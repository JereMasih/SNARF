import functools
import time

# Las 4 Capacidades de Google (Drive/Gmail/Calendar/YouTube) cachean el
# service de googleapiclient en self._service para no reconstruirlo en cada
# llamada — pero un proceso de larga vida (el server real corre días) puede
# terminar con esa conexión rota tras un cambio de red o que la Mac
# durmiera. Visto real en producción: "[SSL] record layer failure" en un
# request de Gmail que hasta un minuto antes venía funcionando.
#
# Un solo reintento (versión anterior de este módulo) no alcanzó en la
# práctica: se confirmó en vivo que el mismo error SSL puede pegarle tanto al
# intento original como al primer reintento (es una falla de red realmente
# intermitente, no una conexión rota de una vez para siempre). Ahora son 3
# intentos en total, con una pausa corta entre cada uno para darle tiempo a
# la falla transitoria de resolverse — sin ocultar un fallo real y
# persistente (ese sigue propagándose después del último intento).
MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 0.4


def retry_with_fresh_client(method):
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        last_exc = None
        for attempt in range(MAX_ATTEMPTS):
            try:
                return method(self, *args, **kwargs)
            except Exception as exc:
                last_exc = exc
                self._service = None
                if attempt < MAX_ATTEMPTS - 1:
                    time.sleep(RETRY_DELAY_SECONDS)
        raise last_exc
    return wrapper
