# Investigación: arquitectura de generación de imágenes para Snarf

**Fecha:** 2026-07-29
**Estado:** Investigación — sin decisión tomada todavía. Este documento compara opciones reales, verificadas contra fuentes actuales (no memoria de entrenamiento sola), para que el fundador decida con datos reales, no supuestos.

## Por qué existe este documento

El fundador pidió que Snarf pueda convertirse en un "Director Creativo" real: generar logos, branding, personajes, concept art, interfaces, thumbnails, portadas, banners, assets, diagramas, presentaciones, material publicitario, storyboards, frames de video — de forma prácticamente ilimitada, con una arquitectura escalable, no una solución improvisada. Antes de tocar código o tomar una decisión, esto compara las alternativas reales del mercado en 2026 contra los criterios que pidió explícitamente: costo, calidad, velocidad, libertad comercial, automatización, integración con Claude Code/agentes, pipelines, generación masiva, edición, consistencia de personaje/marca, y entrenamiento futuro.

## Resumen ejecutivo (para leer en 30 segundos)

No hay una sola opción que gane en todo — por eso esto es una comparación, no una recomendación cerrada:

- **Mejor calidad general / mejor seguimiento de instrucciones y texto en imagen:** GPT Image 2 (OpenAI).
- **Mejor para diagramas, infografías, edición fiel a lo pedido:** Nano Banana Pro / Gemini 3 Pro Image (Google).
- **Mejor para logos y vectores reales (SVG de verdad, no un raster que parece vector):** Recraft V4.1 — es la única opción de esta lista que exporta SVG real.
- **Mejor para texto renderizado dentro de la imagen (carteles, tipografía compleja):** Ideogram 4.0.
- **Mejor para control total, automatización sin límite, entrenamiento de personajes propios (LoRA), y costo marginal cero por imagen una vez montado:** stack self-hosted (ComfyUI + Flux).
- **Midjourney:** fuera de esta comparación como opción seria de integración — no tiene una API pública madura y estándar en 2026 (ver sección dedicada), lo cual choca directo con "automatización" y "agentes", dos de los criterios explícitos del fundador.

## Comparación por opción

### 1. OpenAI — GPT Image 2 (sucesor de GPT Image 1, que se discontinúa el 23 de octubre de 2026)

- **Costo:** con GPT Image 1 el precio iba de ~$0.011 a $0.25 por imagen según calidad/tamaño; GPT Image 2 es el modelo vigente a usar en cualquier integración nueva (GPT Image 1 ya está en discontinuación). [Fuente: aifreeapi.com](https://www.aifreeapi.com/en/posts/openai-image-generation-api-pricing), [gate.ai](https://gate.ai/blog/gpt-image-1-openai-specs-pricing-api-use-cases)
- **Calidad:** líder en los rankings de Artificial Analysis y lmarena para seguimiento de instrucciones (*prompt adherence*) y renderizado de texto (99% de precisión). [Fuente: teamday.ai](https://www.teamday.ai/blog/best-ai-image-models-2026)
- **Libertad comercial:** la licencia comercial viene incluida gratis para clientes de la API — se puede usar el output comercialmente sin costo de licencia aparte. [Fuente: finout.io](https://www.finout.io/blog/openai-pricing-in-2026)
- **Integración:** API REST estándar, misma familia de credenciales que ya usa Snarf para `AnthropicLLM`-equivalentes de otros vendors (Voyage, ElevenLabs) — sería una Capacidad más, mismo patrón.
- **Edición/consistencia:** soporta edición condicionada por imagen (image-to-image), pero no un mecanismo de entrenamiento de personaje propio (no hay LoRA ni fine-tuning de personajes en la API pública).

### 2. Google — Nano Banana Pro (Gemini 3 Pro Image) — reemplaza a Imagen 4, que se apaga el 17 de agosto de 2026

- **Calidad:** líder en las arenas de edición de imagen; el único de esta lista con salida estándar en 4096×4096; se apoya en el conocimiento general de Gemini para diagramas e infografías precisas. [Fuente: teamday.ai](https://www.teamday.ai/blog/best-ai-image-models-2026)
- **Costo:** existe también Nano Banana 2 (más barato) para trabajo de alto volumen sin necesitar la calidad máxima de Pro.
- **Nota importante de vigencia:** Imagen 4 (el modelo que muchas guías todavía mencionan) ya está deprecado — cualquier integración nueva debe apuntar a Nano Banana Pro/2, no a Imagen 4.
- **Integración:** API de Gemini, mismo ecosistema que usa cualquier otra Capacidad de Google ya presente en Snarf (Drive/Gmail/Calendar/YouTube) — de las opciones de este documento, la que más se parece a algo que Snarf "ya sabe hacer" en términos de auth.

### 3. Black Forest Labs — Flux / Flux Kontext

- **Costo (API):** Kontext Pro $0.04/imagen, Kontext Max $0.08/imagen, sin suscripción — pago por uso puro. [Fuente: developer.puter.com](https://developer.puter.com/tutorials/flux-api-pricing/)
- **Costo (self-hosted):** `[schnell]` es gratis y open-source con uso comercial permitido; `[dev]` es gratis solo para uso no-comercial (licencia comercial self-hosted: US$999/mes); `[pro]`/Kontext son API-only. [Fuente: costbench.com](https://costbench.com/software/ai-image-generators/flux/)
- **Edición:** Kontext está diseñado específicamente para edición iterativa condicionada por imagen (cambiar UNA parte de una imagen ya generada, mantener el resto) — el más fuerte de esta lista en ese punto específico.
- **Entrenamiento/consistencia de personaje:** los checkpoints de Flux son los más soportados para LoRA custom (entrenar el aspecto exacto de un personaje propio) en todo el ecosistema self-hosted actual — soporte "día cero" en ComfyUI para cada variante nueva de Flux. [Fuente: local-llm.net](https://www.local-llm.net/compare/comfyui-vs-automatic1111-vs-forge/)

### 4. Ideogram 4.0

- Primer modelo de pesos abiertos (*open-weight*) en meterse en el top 5 global de calidad de imagen; **0.97 de precisión OCR** — el mejor de esta lista para texto renderizado dentro de la imagen (carteles, portadas con tipografía compleja, thumbnails con texto grande). [Fuente: teamday.ai](https://www.teamday.ai/blog/best-ai-image-models-2026)

### 5. Recraft V4.1

- **Único de esta lista que exporta SVG real**, no un raster disfrazado — crítico para un logo que tiene que funcionar tanto gigante como a 32×32px, exactamente el requisito que puso el fundador para el isotipo de Snarf. [Fuente: teamday.ai](https://www.teamday.ai/blog/best-ai-image-models-2026)
- **Costo:** $0.04 por imagen raster, $0.08 por imagen vectorial. [Fuente: wavespeed.ai](https://wavespeed.ai/blog/image-model-access/recraft-api-access-and-pricing/)
- **Funciones de marca:** la API expone explícitamente "brand colors" y consistencia de estilo como parámetros de primera clase — pensado para trabajo de identidad visual, no genérico. [Fuente: recraft.ai](https://www.recraft.ai/blog/discover-the-power-of-recrafts-image-generation-api)
- También soporta edición, quitar fondo, inpainting/outpainting y batch jobs asincrónicos — relevante para "generación masiva".

### 6. Midjourney — la opción a la que hay que ponerle una advertencia real

- **No existe una API pública, oficial y estándar** en el sentido de REST/SDK/webhooks documentados que cualquiera pueda pedir — a inicios de 2026 seguía sin haber un camino de desarrollador estándar. Hubo un anuncio de "Midjourney Official API" a fines de 2025, pero seguía en release limitado a abril de 2026, con **términos comerciales más restrictivos que DALL-E 4 o Imagen 4**. [Fuente: cometapi.com](https://www.cometapi.com/is-midjourney-free-what-to-know-now-a-2026-update/), [10b.ai](https://10b.ai/blog/does-midjourney-have-an-api)
- Sí tiene buena licencia de uso comercial sobre las imágenes generadas por un usuario humano normal (feb. 2026: propiedad general de lo que generás, incluido el derecho a vender). [Fuente: terms.law](https://terms.law/2026/01/15/midjourney-commercial-use-rights-complete-2026-guide/)
- **Conclusión honesta:** Midjourney sigue siendo fuerte para exploración estética manual, pero **no es una opción real para "que cualquier agente pida una imagen mediante herramientas internas"** — ese es justamente el objetivo final que pidió el fundador, y Midjourney no tiene el camino de integración que eso requiere. Cualquier "API de Midjourney" de terceros que aparezca en una búsqueda es un wrapper no oficial, con el riesgo de discontinuación/cambio de términos que eso implica.

### 7. Stack self-hosted: ComfyUI vs Automatic1111 vs Forge vs InvokeAI

Los cuatro corren los mismos modelos por debajo (Stable Diffusion, SDXL, SD3, Flux) — la diferencia real es la interfaz y qué tan bien se presta a automatización:

- **ComfyUI:** presenta la generación como un grafo de nodos (cada paso del pipeline — cargar modelo, encoder de texto, sampler, VAE, ControlNet, LoRA — es un nodo). Soporte día-cero para cada variante nueva de Flux. La comunidad ya construyó miles de workflows reusables, incluyendo consistencia de personaje real vía cadenas de IPAdapter + InstantID + ControlNet + restauración de rostro. [Fuente: local-llm.net](https://www.local-llm.net/compare/comfyui-vs-automatic1111-vs-forge/), [offlinecreator.com](https://offlinecreator.com/compare/comfyui-vs-automatic1111-vs-invokeai-2026)
- **Automatic1111 (A1111):** interfaz de formulario simple (prompt + sliders + botón Generar) — más fácil de aprender, menos apto para pipelines automatizados o integraciones de agente porque no está pensado como grafo programable.
- **Forge:** variante de A1111 optimizada en performance, misma filosofía de interfaz que A1111.
- **InvokeAI:** UI más pulida que ComfyUI, buen soporte de Flux.2 y formatos LoRA de Klein. Term medio entre la simplicidad de A1111 y el poder de ComfyUI.
- **Para el objetivo de Snarf (pipelines, generación masiva, agentes pidiendo imágenes por su cuenta), ComfyUI es la opción con más evidencia real de uso en ese exacto escenario** — ver siguiente sección.

## MCP para generación de imágenes — ya existe, no hay que inventarlo

Esto es directamente relevante para "integración con Claude Code" e "integración futura con agentes", que el fundador pidió investigar explícitamente:

- **`comfyui-mcp` (artokun):** MCP server + plugin de Claude Code, 108 herramientas, 29 "skills" de IA (Flux, WAN, Ideogram4, Krea2, etc.). Corre local, en LAN, en VPS, o en Comfy Cloud. Permite que Claude edite el grafo en vivo en lenguaje natural, no solo dispare generaciones sueltas. [Fuente: GitHub - artokun/comfyui-mcp](https://github.com/artokun/comfyui-mcp)
- **Comfy Cloud MCP (oficial):** servidor MCP oficial de comfy.org — corre en `cloud.comfy.org/mcp`, ejecuta los workflows en GPUs de Comfy Cloud, **sin necesitar hardware propio**. Genera imagen, video, audio y 3D, busca modelos/nodos/templates, y corre workflows completos desde una conversación con el agente. [Fuente: docs.comfy.org](https://docs.comfy.org/agent-tools/mcp), [comfy.org/mcp](https://comfy.org/mcp/)
- Con cualquiera de los dos, Claude ya puede generar imágenes, hacer upscale, correr pipelines de ControlNet, inpainting/outpainting inteligente, transferencia de estilo vía IP-Adapter — todo por conversación natural, sin construir nada de esa integración desde cero. [Fuente: comfyui-wiki.com](https://comfyui-wiki.com/en/news/2026-06-30-comfy-mcp-agent-integration)

**Esto cambia la pregunta de arquitectura**: no es "¿construimos un pipeline de generación de imágenes desde cero?", es "¿usamos el MCP de Comfy Cloud (cero hardware propio, pago por uso de GPU) o el MCP local de ComfyUI (control total, costo marginal ~cero una vez montado, necesita una GPU propia o alquilada)?" — ambos caminos ya existen y están mantenidos por terceros, no hace falta inventar el protocolo de integración.

## Tabla comparativa (según los criterios que pidió el fundador)

| Opción | Costo | Calidad | Velocidad | Libertad comercial | Automatización/pipelines | Consistencia de personaje | Vector/logo real | Integración agente hoy |
|---|---|---|---|---|---|---|---|---|
| GPT Image 2 | Medio (por imagen) | Muy alta (líder en texto/instrucciones) | Alta | Sí, incluida | API estándar | No (sin LoRA propio) | No | API directa |
| Nano Banana Pro | Medio | Muy alta (edición, diagramas) | Alta | Sí | API estándar | No | No | API directa |
| Flux Kontext (API) | Bajo ($0.04-0.08/img) | Alta, fuerte en edición iterativa | Alta | Sí | API estándar | Vía self-host | No | API directa |
| Flux self-hosted | Costo de GPU, no por imagen | Alta (mismo modelo) | Depende del hardware | Sí (schnell) / con costo (dev/pro) | Total (ComfyUI) | **La mejor de esta lista** (LoRA) | No | MCP ya existente |
| Ideogram 4.0 | Medio | Muy alta en texto renderizado | Alta | — (revisar términos) | API | No | No | API directa |
| Recraft V4.1 | Bajo-medio | Alta, foco en diseño/marca | Alta | Sí | API + batch async | Parcial (estilo de marca) | **Sí, único con SVG real** | API directa |
| Midjourney | Medio (plan) | Muy alta estética | Media (colas) | Sí (para uso humano) | **Muy limitada** | No | **No madura** |
| ComfyUI + MCP | Costo de GPU | Depende del modelo cargado | Alta si hay GPU propia | Depende del modelo cargado | **La mejor de esta lista** | **La mejor de esta lista** | No nativo | **Ya construido y mantenido** |

## Cómo encajaría en la arquitectura de Snarf (sin decidir todavía)

Dado que Snarf ya tiene el patrón "Capacidad chica e inyectada, sin lógica de negocio adentro" (`snarf/capabilities/*.py`) para cada vendor externo (Anthropic, ElevenLabs, Voyage, Google), cualquiera de las opciones de API directa (OpenAI, Google, Flux, Ideogram, Recraft) encajaría como **una Capacidad nueva por vendor**, exactamente igual que `ElevenLabsTTS`/`VoyageEmbeddings` hoy — sin inventar un patrón nuevo.

La opción ComfyUI+MCP es arquitectónicamente distinta: en vez de una Capacidad HTTP simple, sería la primera vez que Snarf habla MCP en vez de API directa — y ahí aplica exactamente el criterio ya escrito en `CLAUDE.md` ("MCP solo cuando es la única puerta de entrada real a una fuente externa"): para ComfyUI, un servidor MCP ya construido y mantenido por la comunidad **sí sería la única puerta de entrada real** práctica (reimplementar 108 herramientas de control de grafo a mano no tendría sentido) — sería el primer caso legítimo de MCP en este proyecto, no una excepción a la regla.

## Próximo paso

Este documento no recomienda una sola opción — compara. Las preguntas reales para decidir, una vez que el fundador lea esto:

1. ¿Se prioriza calidad/velocidad de una API paga (sin hardware propio, costo por imagen) o control total + costo marginal casi cero con self-hosted (necesita GPU propia o alquilada)?
2. ¿Cuánto importa la consistencia de un personaje propio entrenado (LoRA) — eso empuja fuerte hacia self-hosted/Flux, ninguna API cerrada lo ofrece hoy?
3. ¿El logo necesita ser vector real (SVG) desde el día uno? Eso apunta directo a Recraft para esa pieza específica, aunque se use otra cosa para el resto.
4. Si se elige self-hosted: ¿local (Mac del fundador, sin costo recurrente pero limitado por su GPU) o Comfy Cloud (sin hardware propio, pago por uso de GPU en la nube)?
