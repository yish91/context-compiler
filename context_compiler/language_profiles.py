from __future__ import annotations

from dataclasses import dataclass, field

IMPORT_TARGET_TYPES: frozenset[str] = frozenset(
    {
        "string",
        "string_fragment",
        "interpreted_string_literal",
        "raw_string_literal",
        "dotted_name",
        "scoped_identifier",
        "namespace_name",
        "qualified_identifier",
    }
)


@dataclass(frozen=True, slots=True)
class LanguageProfile:
    """Table-driven structural extraction rules for a Tree-sitter grammar.

    Adding a language = adding one entry. All structural extraction flows
    through a single generic walker that looks up node types here.
    """

    class_types: frozenset[str] = field(default_factory=frozenset)
    function_types: frozenset[str] = field(default_factory=frozenset)
    import_types: frozenset[str] = field(default_factory=frozenset)
    import_target_types: frozenset[str] = field(default_factory=lambda: IMPORT_TARGET_TYPES)


LANGUAGE_PROFILES: dict[str, LanguageProfile] = {
    "python": LanguageProfile(
        class_types=frozenset({"class_definition"}),
        function_types=frozenset({"function_definition"}),
        import_types=frozenset({"import_statement", "import_from_statement"}),
    ),
    "typescript": LanguageProfile(
        class_types=frozenset({"class_declaration", "interface_declaration"}),
        function_types=frozenset({"function_declaration", "method_definition"}),
        import_types=frozenset({"import_statement"}),
    ),
    "tsx": LanguageProfile(
        class_types=frozenset({"class_declaration", "interface_declaration"}),
        function_types=frozenset({"function_declaration", "method_definition"}),
        import_types=frozenset({"import_statement"}),
    ),
    "javascript": LanguageProfile(
        class_types=frozenset({"class_declaration"}),
        function_types=frozenset({"function_declaration", "method_definition"}),
        import_types=frozenset({"import_statement"}),
    ),
    "go": LanguageProfile(
        class_types=frozenset({"type_spec"}),
        function_types=frozenset({"function_declaration", "method_declaration"}),
        import_types=frozenset({"import_spec"}),
    ),
    "rust": LanguageProfile(
        class_types=frozenset({"struct_item", "enum_item", "trait_item", "impl_item"}),
        function_types=frozenset({"function_item"}),
        import_types=frozenset({"use_declaration"}),
    ),
    "java": LanguageProfile(
        class_types=frozenset(
            {
                "class_declaration",
                "interface_declaration",
                "enum_declaration",
                "record_declaration",
            }
        ),
        function_types=frozenset({"method_declaration", "constructor_declaration"}),
        import_types=frozenset({"import_declaration"}),
    ),
    "csharp": LanguageProfile(
        class_types=frozenset(
            {"class_declaration", "interface_declaration", "struct_declaration", "record_declaration"}
        ),
        function_types=frozenset({"method_declaration", "constructor_declaration"}),
        import_types=frozenset({"using_directive"}),
    ),
    "kotlin": LanguageProfile(
        class_types=frozenset({"class_declaration", "object_declaration"}),
        function_types=frozenset({"function_declaration"}),
        import_types=frozenset({"import_header"}),
    ),
    "swift": LanguageProfile(
        class_types=frozenset(
            {"class_declaration", "protocol_declaration", "struct_declaration", "enum_declaration"}
        ),
        function_types=frozenset({"function_declaration", "init_declaration"}),
        import_types=frozenset({"import_declaration"}),
    ),
    "ruby": LanguageProfile(
        class_types=frozenset({"class", "module"}),
        function_types=frozenset({"method", "singleton_method"}),
        import_types=frozenset(),
    ),
    "php": LanguageProfile(
        class_types=frozenset(
            {"class_declaration", "interface_declaration", "trait_declaration", "enum_declaration"}
        ),
        function_types=frozenset({"function_definition", "method_declaration"}),
        import_types=frozenset({"namespace_use_declaration"}),
    ),
    "cpp": LanguageProfile(
        class_types=frozenset({"class_specifier", "struct_specifier"}),
        function_types=frozenset({"function_definition"}),
        import_types=frozenset({"preproc_include"}),
    ),
    "c": LanguageProfile(
        class_types=frozenset({"struct_specifier"}),
        function_types=frozenset({"function_definition"}),
        import_types=frozenset({"preproc_include"}),
    ),
    "scala": LanguageProfile(
        class_types=frozenset({"class_definition", "object_definition", "trait_definition"}),
        function_types=frozenset({"function_definition"}),
        import_types=frozenset({"import_declaration"}),
    ),
    "dart": LanguageProfile(
        class_types=frozenset({"class_definition", "mixin_declaration", "enum_declaration"}),
        function_types=frozenset({"function_signature", "method_signature"}),
        import_types=frozenset({"import_or_export"}),
    ),
    "lua": LanguageProfile(
        class_types=frozenset(),
        function_types=frozenset({"function_declaration", "local_function"}),
        import_types=frozenset(),
    ),
    "bash": LanguageProfile(
        class_types=frozenset(),
        function_types=frozenset({"function_definition"}),
        import_types=frozenset(),
    ),
    "powershell": LanguageProfile(
        class_types=frozenset({"class_statement"}),
        function_types=frozenset({"function_statement"}),
        import_types=frozenset(),
    ),
}


def get_profile(language: str) -> LanguageProfile | None:
    return LANGUAGE_PROFILES.get(language)
