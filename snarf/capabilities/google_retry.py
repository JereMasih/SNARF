import functools

# Las 4 Capacidades de Google (Drive/Gmail/Calendar/YouTube) cachean el
# service de googleapiclient en self._service para no reconstruirlo en cada
# llamada — pero un proceso de larga vida (el server real corre días) puede
# terminar con esa conexión rota tras un cambio de red o que la Mac
# durmiera. Visto real en producción: "[SSL] record layer failure" en un
# request de Gmail que hasta un minuto antes venía funcionando. Un solo
# reintento con un cliente reconstruido resuelve la enorme mayoría de estos
# casos sin ocultar un fallo real y persistente (ese sí se propaga).


def retry_once_with_fresh_client(method):
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except Exception:
            self._service = None
            return method(self, *args, **kwargs)
    return wrapper
