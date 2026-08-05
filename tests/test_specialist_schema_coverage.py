import sys

# Import real de cada módulo que define una subclase real de Specialist —
# necesario para que Specialist.__subclasses__() la vea (mismo motivo por el
# que TOOL_TO_NODE/VERB_BY_SKILL se verifican contra orchestrator.TOOLS real,
# nunca una lista mantenida a mano por separado).
import snarf.executive.specialist  # noqa: F401
import snarf.specialists.dashboard_curator  # noqa: F401
import snarf.specialists.gmail_digest  # noqa: F401
import snarf.specialists.productivity.calendar_brief  # noqa: F401
import snarf.specialists.content.specialist  # noqa: F401
import snarf.specialists.agency.client_status  # noqa: F401
import snarf.specialists.community.pulse  # noqa: F401
import snarf.specialists.finance.books_categorize  # noqa: F401
import snarf.specialists.finance.monthly_pnl  # noqa: F401
import snarf.specialists.research.specialist  # noqa: F401
import snarf.specialists.sales.sponsor_inbox_triage  # noqa: F401
from snarf.specialists.base import Specialist


def test_every_specialist_declares_input_and_output_schema():
    subclasses = Specialist.__subclasses__()
    assert subclasses, "no se encontró ninguna subclase real de Specialist — revisar los imports de este archivo"
    for cls in subclasses:
        module = sys.modules[cls.__module__]
        assert hasattr(module, "INPUT_SCHEMA"), f"{cls.__module__} no declara INPUT_SCHEMA (ver snarf/specialists/base.py)"
        assert hasattr(module, "OUTPUT_SCHEMA"), f"{cls.__module__} no declara OUTPUT_SCHEMA (ver snarf/specialists/base.py)"
        assert isinstance(module.INPUT_SCHEMA, dict)
        assert isinstance(module.OUTPUT_SCHEMA, dict)
        assert module.INPUT_SCHEMA.get("type") == "object"
        assert module.OUTPUT_SCHEMA.get("type") == "object"
