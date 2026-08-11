import json
import os
import re
import time
from dataclasses import dataclass, replace
from typing import Callable

from snarf.capabilities.base import Capability
from snarf.telemetry import cancellation, context, detail, spans, usage_tracker

DEFAULT_MODEL = "claude-sonnet-5"
MAX_TOOL_ROUNDS = 5
# Antes en 4096: un tope demasiado bajo para el uso real de Snarf (planes,
# documentos largos) que cortaba la respuesta a mitad de camino — y como el
# marcador de habla (---HABLA---) va al final del texto, el corte también
# tiraba abajo el audio (split_speech no encontraba el marcador y caía al
# fallback mecánico de 400 caracteres). Ver MAX_CONTINUATIONS más abajo para
# la red de seguridad si ni así alcanza.
MAX_OUTPUT_TOKENS = 16000
# Reintentos de continuación cuando, pese al tope de arriba, la respuesta
# igual se corta por longitud (documentos muy largos). Cada intento le pide
# al modelo seguir exactamente donde cortó, nunca reescribir desde cero.
MAX_CONTINUATIONS = 2
CACHE_TTL = "1h"

# Marcadores que separan, dentro de un mismo texto generado, la respuesta
# completa (a pantalla) de su narración hablada (a voz) y — cuando corresponde
# — del entregable puntual que la respuesta contiene (un plan, un documento,
# una copia pedida). Ver ADR de la capa de voz + ADR de esta ronda (escuchar
# vs escuchar entregable). El system prompt (orchestrator.SYSTEM_PREFIX)
# instruye al modelo a usar exactamente estos delimitadores; se definen acá
# porque este módulo es el único que los parsea, una sola fuente de verdad.
SPEECH_START = "---HABLA---"
SPEECH_END = "---FIN-HABLA---"
DELIVERABLE_START = "---ENTREGABLE---"
DELIVERABLE_END = "---FIN-ENTREGABLE---"
FALLBACK_SPEECH_MAX_CHARS = 400


@dataclass(frozen=True)
class LLMResponse:
    """Una respuesta generada, separada en pantalla / narración hablada / entregable.

    text: la respuesta íntegra, con estructura/markdown, para mostrar en pantalla.
    speech: narración hablada de ESA MISMA respuesta completa — no es un resumen
    acortado, cubre todo lo sustancial que está en pantalla, fraseado para voz
    (sin markdown, sin URLs deletreadas). Nunca oculta un riesgo o dato faltante.
    deliverable: cuando la respuesta contiene un entregable puntual y pedido
    explícitamente (un plan, un documento, una copia) distinto de la charla
    alrededor, es SOLO ese contenido, fraseado para voz — None si esta
    respuesta es puramente conversacional y no hay nada que aislar.
    thinking: el razonamiento crudo del modelo antes de la respuesta final
    (campo `reasoning` que devuelven algunos modelos locales tipo Qwen3.5 vía
    mlx_lm.server) — None cuando el modelo no expone ese campo (la mayoría:
    Anthropic sin extended thinking habilitado, o un modelo local "instruct"
    no-thinking como el default actual). Nunca se persiste a memoria
    episódica a propósito: es un artefacto de transparencia de ESTA
    respuesta puntual, no parte del historial de la conversación.
    cancelled: True cuando el fundador frenó este pedido a mitad de
    generación (ver snarf/runtime/cancellation.py y ADR de esta ronda) —
    text/speech quedan con lo parcial ya generado hasta el corte, nunca
    inventado más allá de eso.
    """

    text: str
    speech: str
    deliverable: str | None = None
    thinking: str | None = None
    cancelled: bool = False


def fallback_speech(text: str) -> str:
    """Versión hablada aproximada cuando el modelo no incluyó el marcador de habla.

    Puramente mecánico (sin otra llamada al modelo): saca marcado Markdown básico
    y corta en un límite de caracteres razonable, preferentemente en un borde de
    oración. No es tan bueno como una versión pensada por el modelo, pero evita
    leer en voz alta encabezados/asteriscos/backticks crudos.
    """
    stripped = re.sub(r"[#*`_>]|^-\s+", "", text, flags=re.MULTILINE).strip()
    stripped = re.sub(r"\s+", " ", stripped)
    if len(stripped) <= FALLBACK_SPEECH_MAX_CHARS:
        return stripped
    truncated = stripped[:FALLBACK_SPEECH_MAX_CHARS]
    cut = max(truncated.rfind(". "), truncated.rfind("? "), truncated.rfind("! "))
    return (truncated[: cut + 1] if cut > 0 else truncated).strip()


# Búsqueda de marcadores tolerante a espacios/saltos de línea de más — bug
# real visto con el modelo local (Qwen3, menos disciplinado que Claude
# siguiendo un formato literal exacto): emitió "---\nHABLA---" en vez de
# "---HABLA---" (salto de línea entre los guiones y la palabra). El string
# literal no matcheaba, split_speech caía a "sin marcador" y el bloque
# completo —los 4 marcadores crudos incluidos— se mostraba tal cual en
# pantalla. Cada marcador es de la forma "---PALABRA---" (2-3 guiones,
# espacio/salto opcional, la palabra, 2-3 guiones) — un regex tolerante
# sigue reconociéndolo aunque el modelo no reproduzca el string exacto.
def _marker_pattern(word: str) -> "re.Pattern[str]":
    return re.compile(r"-{2,3}\s*" + word.replace("-", r"\s*-\s*") + r"\s*-{2,3}")


_SPEECH_START_RE = _marker_pattern("HABLA")
_SPEECH_END_RE = _marker_pattern("FIN-HABLA")
_DELIVERABLE_START_RE = _marker_pattern("ENTREGABLE")
_DELIVERABLE_END_RE = _marker_pattern("FIN-ENTREGABLE")


def _extract_deliverable(remainder: str) -> str | None:
    """Busca el bloque de entregable en lo que queda después del cierre de habla.

    Ausente en la mayoría de las respuestas (puramente conversacionales) — solo
    aparece cuando el modelo decidió que hay algo puntual para aislar."""
    match = _DELIVERABLE_START_RE.search(remainder)
    if match is None:
        return None
    end_match = _DELIVERABLE_END_RE.search(remainder, match.end())
    block = remainder[match.end() : end_match.start() if end_match else None].strip()
    return block or None


def split_speech(raw_text: str, thinking: str | None = None) -> LLMResponse:
    """Separa el texto crudo del modelo en (text, speech, deliverable) según los delimitadores.

    `thinking` no participa del parseo (no viene mezclado en raw_text, es un
    campo aparte del proveedor) — solo se adjunta tal cual al LLMResponse
    final, para que cada llamador no tenga que reconstruir el objeto a mano."""
    start_match = _SPEECH_START_RE.search(raw_text)
    if start_match is None:
        text = raw_text.strip()
        return LLMResponse(text=text, speech=fallback_speech(text), thinking=thinking)
    text = raw_text[: start_match.start()].rstrip()
    tail = raw_text[start_match.end() :]

    deliverable_match = _DELIVERABLE_START_RE.search(tail)
    # El marcador de entregable, si aparece, siempre marca el final real del
    # contenido hablado — incluso cuando el modelo se olvidó de cerrar
    # FIN-HABLA antes de abrirlo (visto en un caso real: el modelo encadenó
    # ---ENTREGABLE--- directo después de la narración, sin cerrar el
    # marcador anterior). Sin este chequeo, esos marcadores quedaban crudos
    # dentro del audio de "escuchar" y el entregable nunca se extraía.
    speech_region = tail[: deliverable_match.start()] if deliverable_match else tail
    deliverable = _extract_deliverable(tail[deliverable_match.start() :]) if deliverable_match else None

    end_match = _SPEECH_END_RE.search(speech_region)
    speech_block = (speech_region[: end_match.start()] if end_match else speech_region).strip()

    # Red de seguridad (bug real visto con el modelo local, menos disciplinado
    # que Claude siguiendo la instrucción de separar pantalla/habla): a veces
    # el modelo escribe TODO el contenido dentro de ---HABLA---, sin nada
    # antes — "text" quedaría vacío y el fundador vería un globo de chat en
    # blanco pese a que sí hay una respuesta real. Nunca dejar la pantalla
    # vacía: si no hay texto separado, mostrar el mismo contenido que se
    # habría narrado (ya cubre "todo lo sustancial", por instrucción del
    # system prompt) en vez de nada.
    if not text:
        text = speech_block or fallback_speech(raw_text.strip())

    return LLMResponse(text=text, speech=speech_block or fallback_speech(text), deliverable=deliverable, thinking=thinking)


def _mark_cache_breakpoint(message: dict) -> dict:
    """Devuelve una copia del mensaje con cache_control en su último bloque.

    No muta el mensaje original: los mensajes de entrada pueden ser
    reutilizados por quien llama (ver EpisodicMemory.recent en el
    orchestrator), y este marcado es efímero por-llamada.
    """
    content = message.get("content")
    blocks = [{"type": "text", "text": content}] if isinstance(content, str) else [
        dict(block) if isinstance(block, dict) else block for block in content
    ]
    if blocks and isinstance(blocks[-1], dict):
        blocks[-1] = {**blocks[-1], "cache_control": {"type": "ephemeral", "ttl": CACHE_TTL}}
    return {**message, "content": blocks}


class GenerationCancelled(Exception):
    """El fundador frenó este pedido a mitad de generación (ver
    snarf/runtime/cancellation.py). Lleva el texto parcial ya generado hasta
    el corte, para no perderlo — nunca se completa ni se inventa el resto."""

    def __init__(self, request_id: str, partial_text: str = ""):
        super().__init__(f"generación cancelada: {request_id}")
        self.partial_text = partial_text


class AnthropicLLM(Capability):
    name = "anthropic_llm"
    # Defaults a nivel de clase (no solo de __init__): varios tests reales
    # construyen esta clase con `AnthropicLLM.__new__(AnthropicLLM)` para
    # evitar el __init__ real (credenciales, cliente HTTP) y setean a mano
    # solo `_client`/`model` — sin estas, esas instancias no tendrían
    # `_max_output_tokens`/etc. Instancias construidas normalmente las pisan
    # con el valor real pasado a __init__.
    _max_output_tokens = MAX_OUTPUT_TOKENS
    _temperature = None
    _max_continuations = MAX_CONTINUATIONS

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        max_output_tokens: int = MAX_OUTPUT_TOKENS,
        temperature: float | None = None,
        max_continuations: int = MAX_CONTINUATIONS,
    ):
        self.model = model
        # Configuración de generación (Fase 7 del plan de observabilidad/n8n,
        # ADR 0142): defaults = las constantes de siempre, así construir sin
        # estos parámetros (todos los tests existentes, cualquier consumidor
        # que no pase por llm_routing._build) se comporta exactamente igual
        # que antes. `snarf/runtime/llm_routing.py` es quien resuelve el
        # override real por rol (vía generation_config.py) y lo pasa acá.
        self._max_output_tokens = max_output_tokens
        self._temperature = temperature
        self._max_continuations = max_continuations
        self._api_key = os.environ.get("ANTHROPIC_API_KEY")
        self._client = None
        if self._api_key:
            import anthropic

            self._client = anthropic.Anthropic(api_key=self._api_key)

    @property
    def available(self) -> bool:
        return self._client is not None

    def warmup(self) -> None:
        if not self._client:
            return
        try:
            self._client.messages.create(
                model=self.model, max_tokens=1, messages=[{"role": "user", "content": "hola"}]
            )
        except Exception:
            pass

    def _create(self, **kwargs):
        """Única forma real de llamar a messages.create en esta clase: siempre
        vía streaming. La propia SDK de Anthropic rechaza requests NO-streaming
        con max_tokens alto (arriesgan timeout HTTP en una conexión larga) —
        con MAX_OUTPUT_TOKENS ya en 16000, streaming deja de ser opcional.
        Devuelve (response, duration_ms) — la duración real de ESTA ronda, para
        el detalle al click del feed del cerebro (ver ADR de esta ronda).

        Si hay un request_id real en contexto (turno de usuario vía /send,
        ver ADR de esta ronda), itera el stream evento por evento para poder
        chequear cancelación a mitad de camino — `MessageStreamManager.
        __exit__` ya cierra la conexión a Anthropic al salir del `with`
        (confirmado contra el SDK instalado), así que un `raise` acá adentro
        corta la generación de verdad, no solo deja de mostrarla. Sin
        request_id (título de conversación, compactación, todos los tests
        actuales) el comportamiento es idéntico al de siempre: directo a
        get_final_message(), sin iterar nada a mano."""
        request_id = context.get_request_id()
        start = time.monotonic()
        with self._client.messages.stream(**kwargs) as stream:
            if request_id:
                for _event in stream:
                    if cancellation.is_cancelled(request_id):
                        partial = ""
                        try:
                            partial = "".join(
                                block.text
                                for block in stream.current_message_snapshot.content
                                if getattr(block, "type", None) == "text"
                            )
                        except AssertionError:
                            pass  # todavía no llegó ningún evento — no hay snapshot que leer
                        raise GenerationCancelled(request_id, partial_text=partial)
            response = stream.get_final_message()
        return response, (time.monotonic() - start) * 1000

    def _create_and_record(self, **kwargs):
        """Único punto real por el que pasa TODA llamada a Anthropic (Fase 1
        del plan de observabilidad) — abre el span (llm.started), lo cierra
        pase lo que pase (cancelación, error, éxito vía _record_usage) y
        deja el registro de uso/costo real con ese mismo event_id, en vez de
        repetir apertura/cierre en los 3 call sites reales de _create()
        (llamada inicial, continuación por corte de longitud, cierre sin
        tools)."""
        span = spans.start_llm("anthropic", self.model)
        try:
            response, duration_ms = self._create(**kwargs)
        except GenerationCancelled:
            spans.fail(span, reason="cancelled")
            raise
        except Exception as exc:
            spans.fail(span, reason=type(exc).__name__)
            raise
        self._record_usage(response, duration_ms, span=span)
        return response, duration_ms

    def generate(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        tool_handler: Callable[[str, dict], object] | None = None,
        max_tool_rounds: int = MAX_TOOL_ROUNDS,
    ) -> LLMResponse:
        if not self._client:
            raise RuntimeError(
                "ANTHROPIC_API_KEY no configurada. Definila en .env (ver .env.example)."
            )

        # El system prompt de Snarf (FOUNDATION+CONSTITUTION+CHARACTER) es
        # idéntico en cada llamada, en todas las conversaciones — un caso de
        # cacheo casi perfecto. cache_control en el bloque de system cachea
        # también las tools que lo preceden (mismo orden de renderizado:
        # tools -> system -> messages), y no cuesta nada si el prompt es
        # demasiado corto para cachear (simplemente no cachea, sin error).
        # TTL extendido (1h en vez del default de 5 min): Snarf llama a la
        # API directa, no la suscripción de Claude, así que sin esto el
        # cache expira rápido entre usos espaciados del fundador.
        cached_system = [
            {"type": "text", "text": system, "cache_control": {"type": "ephemeral", "ttl": CACHE_TTL}}
        ]

        conversation = list(messages)
        request_id = context.get_request_id()
        for _ in range(max_tool_rounds):
            if request_id and cancellation.is_cancelled(request_id):
                return self._cancelled_response()
            call_messages = list(conversation)
            if call_messages:
                # Segundo punto de cacheo: el historial de la conversación
                # (reconstruido igual en cada turno desde EpisodicMemory) y,
                # dentro de una misma llamada, cada ronda del loop de
                # herramientas — hoy se reprocesaba entero y sin cachear.
                call_messages[-1] = _mark_cache_breakpoint(call_messages[-1])
            kwargs = dict(model=self.model, max_tokens=self._max_output_tokens, system=cached_system, messages=call_messages)
            if self._temperature is not None:
                kwargs["temperature"] = self._temperature
            if tools:
                kwargs["tools"] = tools
            try:
                response, duration_ms = self._create_and_record(**kwargs)
            except GenerationCancelled as exc:
                return self._cancelled_response(exc.partial_text)

            if response.stop_reason == "tool_use" and tool_handler:
                conversation.append({"role": "assistant", "content": response.content})
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = tool_handler(block.name, block.input)
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": json.dumps(result, ensure_ascii=False, default=str),
                            }
                        )
                conversation.append({"role": "user", "content": tool_results})
                continue

            text = "".join(block.text for block in response.content if block.type == "text")
            continuations = 0
            while response.stop_reason == "max_tokens" and continuations < self._max_continuations:
                # Red de seguridad real: pese a MAX_OUTPUT_TOKENS=16000 la
                # respuesta se sigue cortando (documento muy largo). En vez de
                # perder lo que sigue, se le pide al modelo continuar EXACTO
                # donde cortó — nunca reescribir desde cero — y se concatena.
                # El marcador de habla (---HABLA---) va al final, así que
                # split_speech recién corre sobre el texto ya completo, más
                # abajo.
                continuations += 1
                conversation.append({"role": "assistant", "content": response.content})
                conversation.append(
                    {
                        "role": "user",
                        "content": (
                            "Tu respuesta anterior se cortó por el límite de longitud. "
                            "Continuá exactamente desde donde cortaste — no repitas nada "
                            "de lo ya escrito, no agregues una introducción nueva."
                        ),
                    }
                )
                call_messages = list(conversation)
                call_messages[-1] = _mark_cache_breakpoint(call_messages[-1])
                try:
                    continuation_kwargs = dict(
                        model=self.model, max_tokens=self._max_output_tokens, system=cached_system, messages=call_messages
                    )
                    if self._temperature is not None:
                        continuation_kwargs["temperature"] = self._temperature
                    response, duration_ms = self._create_and_record(**continuation_kwargs)
                except GenerationCancelled as exc:
                    return self._cancelled_response(text + exc.partial_text)
                text += "".join(block.text for block in response.content if block.type == "text")

            if response.stop_reason == "max_tokens":
                # Se agotaron también los reintentos de continuación — recién
                # acá se admite el corte, en vez de asumirlo de entrada.
                text += "\n\n*(respuesta truncada: llegó al límite de longitud incluso después de continuar)*"
            return split_speech(text)

        # Se agotaron las rondas de herramientas sin llegar a una respuesta
        # final. Antes esto devolvía un mensaje de fallo genérico que
        # descartaba todo lo ya reunido en las rondas anteriores (bug real
        # reportado: un turno entero perdido, sin comunicar nada útil al
        # fundador). Ahora se fuerza una última llamada SIN tools — el
        # modelo no puede seguir pidiendo herramientas, así que tiene que
        # sintetizar en prosa lo que ya juntó y decir qué quedó pendiente.
        closing_messages = list(conversation)
        if closing_messages:
            closing_messages[-1] = _mark_cache_breakpoint(closing_messages[-1])
        closing_messages.append(
            {
                "role": "user",
                "content": (
                    "Se agotaron los intentos de usar herramientas antes de llegar a una "
                    "respuesta final. Con lo que ya reuniste en los pasos anteriores, dame "
                    "la mejor respuesta posible ahora mismo, en prosa, sin pedir ninguna "
                    "herramienta más — y decime explícitamente qué quedó sin resolver."
                ),
            }
        )
        try:
            closing_kwargs = dict(
                model=self.model, max_tokens=self._max_output_tokens, system=cached_system, messages=closing_messages
            )
            if self._temperature is not None:
                closing_kwargs["temperature"] = self._temperature
            response, duration_ms = self._create_and_record(**closing_kwargs)
            text = "".join(block.text for block in response.content if block.type == "text")
            if text.strip():
                return split_speech(text)
        except GenerationCancelled as exc:
            return self._cancelled_response(exc.partial_text)
        except Exception:
            pass

        timeout_text = "[demasiadas consultas a herramientas, no llegué a una respuesta final]"
        return LLMResponse(text=timeout_text, speech=timeout_text)

    def _cancelled_response(self, partial_text: str = "") -> LLMResponse:
        """El fundador frenó el pedido (ver GenerationCancelled más arriba).
        Con texto parcial real, se procesa igual que cualquier respuesta
        (separa habla/entregable) y se marca cancelled=True; sin nada
        generado todavía, un texto honesto de que no llegó a responder —
        nunca se inventa contenido más allá de lo que el modelo alcanzó a
        escribir antes del corte."""
        text = partial_text.strip()
        if not text:
            text = "[pedido cancelado antes de generar una respuesta]"
            return LLMResponse(text=text, speech=text, cancelled=True)
        return replace(split_speech(text), cancelled=True)

    def _record_usage(self, response, duration_ms: float | None = None, span=None) -> None:
        usage = getattr(response, "usage", None)
        if usage is None:
            # Edge case real solo visto en tests con fakes incompletos — en
            # producción `usage` siempre viene. Si había un span abierto
            # (ver _create_and_record), hay que cerrarlo igual: sin esto
            # quedaría un llm.started sin su llm.finished, huérfano para
            # siempre en telemetry_events.jsonl.
            if span is not None:
                spans.finish(span, estado="completo")
            return
        # Texto real ya generado en esta ronda (mismo slice que hace la
        # respuesta final más abajo) — nunca una llamada nueva al modelo,
        # solo lo que el propio response ya trae (ver ADR 0089, campo
        # `detalle`). Vacío en rondas puramente de tool_use, sin texto.
        text = "".join(block.text for block in response.content if getattr(block, "type", None) == "text")
        usage_tracker.record_anthropic_call(
            self.model,
            getattr(usage, "input_tokens", 0) or 0,
            getattr(usage, "output_tokens", 0) or 0,
            getattr(usage, "cache_creation_input_tokens", 0) or 0,
            getattr(usage, "cache_read_input_tokens", 0) or 0,
            stop_reason=getattr(response, "stop_reason", None),
            detalle=detail.truncate_detalle(text),
            duration_ms=duration_ms,
            span=span,
        )
