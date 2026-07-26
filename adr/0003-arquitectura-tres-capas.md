# ADR 0003 — Arquitectura de tres capas cognitivas

**Fecha:** 2026-07-25
**Estado:** Aceptado

## Contexto

BUILD MODE 001 definió que Snarf debe distinguir Capacidades (ejecutan), Especialistas Cognitivos (razonan sin identidad propia) y Snarf (única identidad que decide, integra y responde). Esta distinción necesita reflejarse en la estructura del código, no solo en la documentación, para que sea real y no decorativa.

## Decisión

Se estructura `snarf/` en tres módulos con contratos (interfaces) explícitos:

- `snarf/capabilities/`: protocolo `Capability`. Cada adaptador (LLM, TTS, STT, futuras APIs) implementa este contrato y no conoce nada del resto del sistema.
- `snarf/specialists/`: protocolo `Specialist` y un registro. Vacío por ahora — no se crea ningún especialista ficticio sin un dominio real que lo justifique.
- `snarf/core/`: el orquestador (`orchestrator.py`), que carga la identidad (Foundation, Constitution, Character), consulta memoria, decide qué especialista o capacidad usar, y es el único módulo que puede hablar con el Runtime.
- `snarf/runtime/`: protocolo `Channel`. Traduce entrada/salida de un canal concreto (texto, voz) al formato que el Core entiende. El Runtime nunca decide ni razona.

## Consecuencias

- Agregar un especialista o una capacidad nueva no requiere tocar el Core ni el Runtime, solo implementar el contrato correspondiente y registrarlo.
- El Core es el único lugar del código con acceso a los documentos de identidad — ninguna Capacidad ni Especialista los lee directamente, preservando que la identidad reside únicamente en Snarf (Constitution, Artículo IV).
