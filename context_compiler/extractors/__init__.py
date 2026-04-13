from __future__ import annotations

from dataclasses import replace

from ..models import ExtractedProject, ScanInput, SourceFile
from ..tree_sitter_runtime import parse_source
from .config_refs import extract_config_refs
from .imports import extract_imports
from .symbols import extract_doc_signals, extract_symbols


def extract_structure(scan_input: ScanInput) -> ExtractedProject:
    symbols = []
    imports = []
    config_refs = []
    doc_signals = []
    for source_file in scan_input.files:
        source = source_file.source_bytes or source_file.absolute_path.read_bytes()
        try:
            tree = parse_source(source_file.language, source)
        except LookupError:
            continue
        symbols.extend(extract_symbols(tree, source_file, source))
        imports.extend(extract_imports(tree, source_file, source))
        config_refs.extend(extract_config_refs(tree, source_file, source))
        doc_signals.extend(extract_doc_signals(tree, source_file, source))
    project = ExtractedProject(
        root=scan_input.root,
        files=list(scan_input.files),
        framework_hints=scan_input.framework_hints,
        symbols=symbols,
        import_edges=imports,
        config_refs=config_refs,
        doc_signals=doc_signals,
    )
    from ..script_support import enrich_script_support

    return enrich_script_support(scan_input, project)


def extract_project(scan_input: ScanInput) -> ExtractedProject:
    from ..language_packs import run_language_packs
    from .components import extract_components
    from .endpoints import extract_endpoints
    from .models import extract_models

    base = extract_structure(scan_input)
    baseline = replace(
        base,
        endpoints=extract_endpoints(scan_input, base),
        data_models=extract_models(scan_input, base),
        components=extract_components(scan_input, base),
    )
    return run_language_packs(scan_input, baseline)


__all__ = ["extract_structure", "extract_project", "SourceFile"]
