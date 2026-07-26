# ADR 0002 — Elección de stack técnico inicial

**Fecha:** 2026-07-25
**Estado:** Aceptado

## Contexto

BUILD MODE 001 exige comenzar la construcción real del Core Cognitivo, el Runtime de interacción y las Capacidades (voz, LLM), sin depender todavía de credenciales externas para poder avanzar. El Principio de Abstracción exige que esta elección sea reemplazable sin afectar la identidad de Snarf.

## Decisión

Se adopta Python 3 como lenguaje del Core, Runtime, Especialistas y adaptadores de Capacidades. Justificación objetiva: es el lenguaje con mayor soporte de SDKs oficiales y comunitarios para los proveedores ya identificados (Anthropic, ElevenLabs, Whisper/OpenAI), tiene el menor costo de cambio de proveedor de modelo (las interfaces de estos SDKs son uniformes), y es razonable de mantener e iterar por una sola persona durante años.

## Consecuencias

- Todo el código vive bajo `snarf/`, con `main.py` como punto de entrada.
- Cambiar de proveedor de modelo o de voz implica reemplazar un adaptador dentro de `snarf/capabilities/`, nunca tocar `snarf/core/` — esto es lo que operacionaliza el Principio de Abstracción (identidad estable, implementación reemplazable).
- Esta decisión es reversible: no hay ningún dato ni documento de identidad atado a Python; solo el código de implementación lo está.
