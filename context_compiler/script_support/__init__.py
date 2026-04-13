from __future__ import annotations

from dataclasses import replace

from ..models import ExtractedProject, ScanInput
from .bash import extract_bash_facts
from .cmd import extract_cmd_facts
from .powershell import extract_powershell_facts


def enrich_script_support(scan_input: ScanInput, project: ExtractedProject) -> ExtractedProject:
    extra_symbols = []
    extra_imports = []
    extra_config_refs = []

    for source_file in scan_input.files:
        try:
            if source_file.language == "bash":
                facts = extract_bash_facts(source_file)
            elif source_file.language == "powershell":
                facts = extract_powershell_facts(source_file)
            elif source_file.language == "cmd":
                facts = extract_cmd_facts(source_file)
            else:
                continue
            extra_symbols.extend(facts.get("symbols", []))
            extra_imports.extend(facts.get("imports", []))
            extra_config_refs.extend(facts.get("config_refs", []))
        except Exception:
            continue

    if not extra_symbols and not extra_imports and not extra_config_refs:
        return project

    return replace(
        project,
        symbols=project.symbols + extra_symbols,
        import_edges=project.import_edges + extra_imports,
        config_refs=project.config_refs + extra_config_refs,
    )
