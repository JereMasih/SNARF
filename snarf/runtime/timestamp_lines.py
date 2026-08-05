"""Filtro de stdin a stdout que antepone timestamp a cada línea.

uvicorn (access log y error log) no trae timestamp por línea por defecto —
confirmado en vivo el 2026-08-05 diagnosticando por qué el server parecía
"colgado": sin timestamp no había forma de saber cuánto había tardado un
`POST /send` real contra el modelo local. Se usa como filtro de pipe en el
LaunchAgent (`com.snarf.server.plist`) en vez de tocar la config de logging
de uvicorn — así cubre CUALQUIER línea que el proceso escriba a stdout/stderr
(access log, error log, cualquier `print()` de la app), no solo una fuente.
"""

import sys
import time


def main() -> None:
    for line in sys.stdin:
        sys.stdout.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {line}")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
