from __future__ import annotations

import logging

from ..models import ExtractedProject, ScanInput

logger = logging.getLogger(__name__)


def run_language_packs(scan_input: ScanInput, project: ExtractedProject) -> ExtractedProject:
    from .go import enrich_go
    from .java import enrich_java
    from .python import enrich_python
    from .typescript import enrich_typescript

    for pack in (enrich_typescript, enrich_python, enrich_go, enrich_java):
        try:
            project = pack(scan_input, project)
        except Exception:
            logger.warning("language pack %s failed", pack.__name__, exc_info=True)
    return project
