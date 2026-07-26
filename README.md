# Snarf — walking skeleton

Para el contexto completo del proyecto: FOUNDATION.md, PROJECT_CONTEXT.md, MASTER_MAP.md, CONSTITUTION.md, CHARACTER.md, COGNITION.md. Decisiones de arquitectura en `adr/`. Historial de cambios en `CHANGELOG.md`.

## Requisitos

- Python 3.10+

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Completá `.env` con tus credenciales. Sin `ANTHROPIC_API_KEY`, Snarf corre en modo eco: la arquitectura funciona de punta a punta, pero sin razonamiento real (ver COGNITION.md).

## Uso

Tres formas equivalentes de hablar con Snarf, todas sobre el mismo Core y la misma memoria:

```bash
python3 main.py           # texto por terminal
python3 main.py --voice   # voz por terminal (Enter para empezar/terminar de hablar)
python3 app.py            # interfaz visual — abrir http://127.0.0.1:8000 en el navegador
```

Accesible también desde el iPhone (u otro dispositivo del mismo tailnet) en **https://macbook-pro-de-jeremas.tailb10c73.ts.net/** — HTTPS real vía Tailscale, necesario para que el navegador autorice el micrófono. Requiere que `python3 app.py` esté corriendo en la Mac y Tailscale conectado (`tailscale serve --bg 8000` ya queda configurado; sobrevive a reinicios del servidor, no de la Mac). Ver `adr/0008`.

Memoria persistente en `data/episodic_memory.jsonl`, compartida entre los tres canales.

## Estado

Texto, voz por terminal e interfaz visual verificados de punta a punta con credenciales reales (backend probado por API; el flujo de grabación del navegador todavía no se probó manualmente en un navegador real). Ver `adr/0004` a `adr/0007`.
