import threading

import pytest

from snarf.capabilities.google_calendar import GoogleCalendar
from snarf.capabilities.google_drive import GoogleDrive
from snarf.capabilities.google_gmail import GoogleGmail
from snarf.capabilities.google_youtube import GoogleYouTube

# FastAPI corre cada endpoint sync en un thread del threadpool, y el
# dashboard dispara varios widgets en paralelo — un solo `self._service`
# compartido entre threads corrompía la conexión SSL/socket subyacente
# (reproducido real: "[SSL] record layer failure" bajo llamadas
# concurrentes). Estos tests confirman que cada thread ve su propio
# `_service`, nunca el de otro thread.

CAPABILITY_CLASSES = [GoogleDrive, GoogleGmail, GoogleCalendar, GoogleYouTube]


@pytest.mark.parametrize("cls", CAPABILITY_CLASSES)
def test_service_is_isolated_per_thread(cls):
    cap = cls.__new__(cls)
    cap._service = "main-thread-service"

    seen_in_other_thread = {}

    def worker():
        seen_in_other_thread["before_set"] = cap._service
        cap._service = "other-thread-service"
        seen_in_other_thread["after_set"] = cap._service

    t = threading.Thread(target=worker)
    t.start()
    t.join()

    assert seen_in_other_thread["before_set"] is None  # nunca ve el service del thread principal
    assert seen_in_other_thread["after_set"] == "other-thread-service"
    assert cap._service == "main-thread-service"  # el thread principal no fue afectado por el otro thread


@pytest.mark.parametrize("cls", CAPABILITY_CLASSES)
def test_service_setter_works_without_init_having_run(cls):
    # Los tests existentes de cada Capacidad construyen vía __new__ (sin
    # pasar por __init__) y asignan _service directo — el helper interno de
    # almacenamiento por thread tiene que tolerar eso sin AttributeError.
    cap = cls.__new__(cls)
    cap._service = "fake-service"
    assert cap._service == "fake-service"
