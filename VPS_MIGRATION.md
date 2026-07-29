# Migración de Snarf a un VPS — runbook

**Estado:** preparación, sin ejecutar. Nada de este documento provisionó ni tocó ningún servidor real — es la guía para cuando el fundador tenga el VPS y decida arrancar (ítem 4 de la Fundación técnica, ver `MASTER_MAP.md`).

## Por qué (contexto real, no solo "es mejor")

Hoy Snarf corre en la Mac del fundador y se accede remoto vía **Tailscale** (`https://macbook-pro-de-jeremas.tailb10c73.ts.net/`, ver ADR 0008). El fundador reportó que la interfaz se siente lenta incluso antes de que existiera la indexación de Drive, accediendo desde el celular. Tailscale en sí no agrega demora relevante (tráfico directo entre dispositivos del tailnet, sin pasar por terceros — ADR 0008), así que la causa más probable es la Mac funcionando como servidor casero: subida de internet residencial típicamente mucho más lenta que la de un datacenter, más el hecho de que la misma máquina donde corre el chat también corre trabajo pesado en segundo plano (indexación, ffmpeg). Un VPS en un datacenter real ataca ambas causas.

## Decisión recomendada: seguir usando Tailscale, ahora desde el VPS

No hace falta comprar un dominio ni configurar `nginx` + Let's Encrypt todavía. Tailscale se instala igual en Linux — el VPS se une al mismo tailnet del fundador, y `tailscale serve` expone la app con HTTPS real, exactamente como hoy en la Mac. Mismo mecanismo ya probado, cero curva de aprendizaje nueva, cero costo adicional.

**Cuándo reconsiderar esto:** cuando exista un segundo usuario real que no sea parte del tailnet del fundador (ítem 5 de la Fundación, o Capacidades de multi-usuario más adelante) — ahí sí va a hacer falta una URL pública de verdad (dominio + certificado propio), porque Tailscale por diseño limita el acceso a dispositivos del propio tailnet (ADR 0008). No es una tarea de hoy.

## Checklist de la migración (cuando el fundador tenga el VPS)

1. **Elegir el VPS**: Linux, no Windows (ver conversación del 2026-07-28 — todo el stack, `ffmpeg` incluido, corre nativo en Linux sin fricción, y sale más barato). Ubuntu LTS es la opción más simple de administrar y con más documentación disponible. Especificaciones mínimas razonables: 2 vCPU, 4GB RAM — la carga real hoy es sobre todo I/O (red, disco), no cómputo pesado, salvo durante la indexación de video.

2. **Dependencias de sistema** (una vez, al aprovisionar):
   ```bash
   sudo apt update
   sudo apt install -y python3.13 python3.13-venv ffmpeg git
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up
   ```

3. **Traer el código**: `git clone https://github.com/JereMasih/SNARF.git` (público, sin secretos — ver ADR 0021).

4. **Recrear lo que `.gitignore` excluye a propósito** — nada de esto viaja por git, hay que copiarlo a mano y de forma segura (ej. `scp`, nunca por chat ni email):
   - `.env` (todas las API keys: Anthropic, ElevenLabs, Voyage, `SNARF_ACCESS_PASSWORD`, `SESSION_SECRET`)
   - `credentials/` completa (`google_client_secret.json` y los tokens por usuario)
   - `data/` completa, si se quiere preservar memoria episódica, el índice de Drive ya construido y los archivos locales — si no se copia, Snarf arranca "en blanco" y hay que re-indexar Drive desde cero (con el costo real que eso implica, ya medido: ver ADR 0028/0030)

5. **Instalar y levantar**:
   ```bash
   python3.13 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   tailscale serve --bg 8000
   ```

6. **Que sobreviva reinicios y no dependa de una terminal abierta** — a diferencia de la Mac (donde hoy `python3 app.py` corre a mano), en un servidor esto tiene que ser un servicio real:
   ```ini
   # /etc/systemd/system/snarf.service
   [Unit]
   Description=Snarf
   After=network.target

   [Service]
   Type=simple
   User=snarf
   WorkingDirectory=/home/snarf/SNARF
   ExecStart=/home/snarf/SNARF/.venv/bin/python3 app.py
   Restart=on-failure
   EnvironmentFile=/home/snarf/SNARF/.env

   [Install]
   WantedBy=multi-user.target
   ```
   `sudo systemctl enable --now snarf` — con esto, un reinicio del VPS no requiere que el fundador haga nada.

7. **Endurecimiento encontrado al preparar este runbook, ya aplicado** (2026-07-29): la cookie de sesión ahora se marca `secure=True` además de `httponly=True, samesite="lax"` — defensa en profundidad, no depender de que Tailscale sea la única capa. Los `TestClient` de los tests pasaron a usar `base_url="https://testserver"` para poder seguir probando el flujo de login con la cookie marcada `Secure`. Nada que hacer acá al migrar — ya está en el código.

## Lo que NO cambia con la migración

`app.py` no necesita modificarse — Tailscale sigue actuando como proxy HTTPS delante del servidor HTTP local, igual que hoy (ADR 0008). El código de Snarf es agnóstico de dónde corre.
