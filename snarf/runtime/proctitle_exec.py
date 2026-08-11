"""Wrapper genérico para darle un nombre de proceso reconocible (Activity
Monitor/ps/top) a un módulo de terceros invocado como `python -m <módulo>
<args>` — pedido real del fundador (2026-08-10) para poder distinguir a
simple vista los servers reales de Snarf (MLX local, Kokoro TTS) de
cualquier otro proceso Python en su Mac.

Por qué esto y no `exec -a <nombre>` desde el shell del LaunchAgent
(intentado primero, y descartado con evidencia real): el build de Python
usado acá (Homebrew, Python.framework con el launcher "Python.app") resetea
el argv[0] que `exec -a` deja seteado ANTES de que Python termine de
arrancar — confirmado en vivo: `exec -a nombre /bin/sleep` sí cambia el
nombre visible en `ps`, pero `exec -a nombre .venv/bin/python -m X` no.
`setproctitle`, en cambio, corre DESDE ADENTRO del proceso Python ya vivo
(después de que ese reseteo ya pasó), así que sí sobrevive — verificado
también en vivo.

Uso real (ver snarf/runtime launchd plists, ej. com.snarf.mlx-fast.plist):
    python -m snarf.runtime.proctitle_exec snarf-mlx-fast mlx_lm server --model ... --port ...
equivale exactamente a:
    python -m mlx_lm server --model ... --port ...
salvo que el proceso aparece como "snarf-mlx-fast" en vez de "Python"."""

import runpy
import sys


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("uso: python -m snarf.runtime.proctitle_exec <nombre> <módulo> [args...]")
    title, module, *module_args = sys.argv[1:]

    import setproctitle

    setproctitle.setproctitle(title)
    sys.argv = [module] + module_args
    runpy.run_module(module, run_name="__main__")


if __name__ == "__main__":
    main()
