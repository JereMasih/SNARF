# ADR 0100 — Harness: nombrar el ciclo de vida real ya existente, más `compare()`

**Fecha:** 2026-08-04
**Estado:** Aceptado

## Contexto

Fase F del plan de expansión "Inteligencia Ejecutiva". El plan original pedía un Harness con
inyección de contexto por skill, validación/tests automáticos por llamada, comparación entre
modelos y reintento ante falla de calidad — gobernando la ejecución entre el Orchestrator y cada
Capacidad/Especialista. Revisando el código real antes de construir nada, casi todo esto ya existe,
repartido sin un nombre común: prompt caching (ADR 0026/0036), confirmación en dos pasos (ADR 0015),
`_bulk_read_gate` (ADR 0067), logs unificados (ADR 0029/0077), alerta de costo (ADR 0081), ruteo
multi-proveedor (ADR 0068), y el reintento ya existente de `AnthropicLLM.generate()` al agotar
rondas de herramientas.

## Decisión

1. **`HARNESS.md` (nuevo, repo root, mismo nivel que `KNOWLEDGE.md`)**: documenta el ciclo de vida
   real de una llamada a herramienta, mapeando cada función pedida por el plan a su mecanismo real
   ya existente. Es sobre todo un ejercicio de nombrar, no de construir.
2. **Pushback deliberado al alcance pedido, con el mismo criterio que ya usaron otras ADRs de este
   repo para no anticipar**: no se construye validación/tests automáticos por skill ni selección
   automática de "ganador" entre proveedores en esta ronda — no hay todavía un caso de falla real y
   concreto contra el cual diseñar esa validación (los consumidores serían las Skills de la Fase I,
   que todavía no existen). Queda nombrado en Roadmaps.
3. **`snarf/runtime/harness.py::compare(system, messages, providers)`** — lo único genuinamente
   nuevo: corre el mismo prompt contra N proveedores reales (`providers: {provider: model}`, elegido
   a propósito por quien llama, nunca adivinado) y devuelve las N respuestas reales para inspección
   manual — sin juez-LLM automático, sin selección de ganador. Un proveedor sin credencial real o
   que falla queda reflejado en su propia entrada (`ComparisonResult.error`), nunca oculta el
   resultado de los demás.
4. **`compare()` se mantiene deliberadamente independiente del trabajo de fallback automático entre
   proveedores que otra sesión está construyendo en paralelo sobre este mismo `llm_routing.py`**
   (`generate_with_fallback`/`build_resilient_llm`/`RECOMMENDED_MODEL`, real y funcional en el
   working tree a la fecha, pero todavía no comiteado por su propia sesión): `compare()` usa
   únicamente primitivas ya comiteadas de `llm_routing.py` (`PROVIDER_PRESETS`) más un helper propio
   y chico (`_build_provider`), en vez de importar los símbolos nuevos de ese trabajo en curso — así
   este commit queda autocontenido y no depende de que el otro trabajo se comitee primero (mismo
   criterio de aislamiento ya aplicado en ADR 0098). Cuando ese trabajo quede comiteado, unificar
   `_build_provider` con el `_build` real de `llm_routing.py` es una limpieza chica y futura, no algo
   que forzar ahora.

## Verificado

- 4 tests nuevos (`tests/test_harness.py`): un resultado real por proveedor pedido; un proveedor sin
  credencial no afecta a los demás; una falla real de un proveedor se refleja en su propia entrada
  sin romper el resto; lista vacía de proveedores devuelve lista vacía.
- 794/794 tests de la suite completa (ejecutados contra el working tree real, que en este momento
  también incluye el trabajo en curso, todavía sin comitear, de la otra sesión).

## Consecuencias

- Ningún mecanismo real de gobernanza de ejecución cambia de comportamiento — este documento y este
  módulo son aditivos, de solo lectura sobre lo que ya corre.
- `HARNESS.md` queda como el punto de referencia único para "qué gobierna una llamada a
  herramienta" — evita que una futura sesión reconstruya, sin saberlo, algo que ya existe con otro
  nombre.
