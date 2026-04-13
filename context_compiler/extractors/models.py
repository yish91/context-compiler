from __future__ import annotations

from ..models import DataModel, ExtractedProject, ScanInput, SourceFile
from ..tree_sitter_runtime import node_text, parse_source

PYTHON_MODEL_BASES = {"BaseModel", "TypedDict", "Model", "Base", "DeclarativeBase"}
PYTHON_MODEL_DECORATORS = {"dataclass", "dataclasses.dataclass", "attr.s", "attrs.define"}


def extract_models(scan_input: ScanInput, project: ExtractedProject) -> list[DataModel]:
    models: list[DataModel] = []
    for source_file in scan_input.files:
        source = source_file.source_bytes or source_file.absolute_path.read_bytes()
        if source_file.language == "python":
            models.extend(_python_models(source_file, source))
        elif source_file.language == "go":
            models.extend(_go_models(source_file, source))
        elif source_file.language in {"typescript", "tsx"}:
            models.extend(_ts_models(source_file, source))
    return models


def _python_models(source_file: SourceFile, source: bytes) -> list[DataModel]:
    tree = parse_source(source_file.language, source)
    out: list[DataModel] = []

    def handle_class(class_node, decorators: list[str]) -> None:
        name: str | None = None
        bases: list[str] = []
        for child in class_node.children:
            if child.type == "identifier" and name is None:
                name = node_text(source, child)
            elif child.type == "argument_list":
                for arg in child.children:
                    if arg.type == "identifier":
                        bases.append(node_text(source, arg))
                    elif arg.type == "attribute":
                        bases.append(node_text(source, arg))
        if name is None:
            return
        is_model = any(base in PYTHON_MODEL_BASES for base in bases) or any(
            dec in PYTHON_MODEL_DECORATORS for dec in decorators
        )
        if not is_model:
            return
        fields = _python_class_fields(class_node, source)
        out.append(
            DataModel(
                name=name,
                kind="class",
                fields=fields,
                source_path=source_file.relative_path,
                line=class_node.start_point[0] + 1,
            )
        )

    def visit(node) -> None:
        if node.type == "decorated_definition":
            decorators: list[str] = []
            class_child = None
            for child in node.children:
                if child.type == "decorator":
                    text = node_text(source, child).lstrip("@").strip()
                    decorators.append(text.split("(")[0])
                elif child.type == "class_definition":
                    class_child = child
            if class_child is not None:
                handle_class(class_child, decorators)
        elif node.type == "class_definition":
            handle_class(node, [])
        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return out


def _python_class_fields(class_node, source: bytes) -> list[str]:
    fields: list[str] = []
    for child in class_node.children:
        if child.type != "block":
            continue
        for stmt in child.children:
            if stmt.type == "expression_statement" and stmt.child_count:
                inner = stmt.children[0]
                if inner.type == "assignment":
                    name_node = inner.children[0] if inner.children else None
                    if name_node is not None and name_node.type == "identifier":
                        fields.append(node_text(source, name_node))
            elif stmt.type == "assignment":
                name_node = stmt.children[0] if stmt.children else None
                if name_node is not None and name_node.type == "identifier":
                    fields.append(node_text(source, name_node))
    return fields


def _go_models(source_file: SourceFile, source: bytes) -> list[DataModel]:
    tree = parse_source("go", source)
    out: list[DataModel] = []

    def visit(node) -> None:
        if node.type == "type_declaration":
            for child in node.children:
                if child.type == "type_spec":
                    name: str | None = None
                    is_struct = False
                    fields: list[str] = []
                    for sub in child.children:
                        if sub.type == "type_identifier":
                            name = node_text(source, sub)
                        elif sub.type == "struct_type":
                            is_struct = True
                            fields = _go_struct_fields(sub, source)
                    if name is not None and is_struct:
                        out.append(
                            DataModel(
                                name=name,
                                kind="struct",
                                fields=fields,
                                source_path=source_file.relative_path,
                                line=child.start_point[0] + 1,
                            )
                        )
        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return out


def _go_struct_fields(struct_node, source: bytes) -> list[str]:
    fields: list[str] = []
    for child in struct_node.children:
        if child.type != "field_declaration_list":
            continue
        for decl in child.children:
            if decl.type == "field_declaration":
                for sub in decl.children:
                    if sub.type == "field_identifier":
                        fields.append(node_text(source, sub))
    return fields


def _ts_models(source_file: SourceFile, source: bytes) -> list[DataModel]:
    tree = parse_source(source_file.language, source)
    out: list[DataModel] = []

    def visit(node) -> None:
        if node.type == "interface_declaration":
            name: str | None = None
            fields: list[str] = []
            for child in node.children:
                if child.type == "type_identifier" and name is None:
                    name = node_text(source, child)
                elif child.type in ("interface_body", "object_type"):
                    fields.extend(_ts_object_fields(child, source))
            if name is not None:
                out.append(
                    DataModel(
                        name=name,
                        kind="interface",
                        fields=fields,
                        source_path=source_file.relative_path,
                        line=node.start_point[0] + 1,
                    )
                )
        elif node.type == "type_alias_declaration":
            name = None
            fields: list[str] = []
            for child in node.children:
                if child.type == "type_identifier" and name is None:
                    name = node_text(source, child)
                elif child.type == "object_type":
                    fields.extend(_ts_object_fields(child, source))
            if name is not None and fields:
                out.append(
                    DataModel(
                        name=name,
                        kind="type",
                        fields=fields,
                        source_path=source_file.relative_path,
                        line=node.start_point[0] + 1,
                    )
                )
        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return out


def _ts_object_fields(body_node, source: bytes) -> list[str]:
    fields: list[str] = []
    for member in body_node.children:
        if member.type == "property_signature":
            for sub in member.children:
                if sub.type == "property_identifier":
                    fields.append(node_text(source, sub))
                    break
    return fields
