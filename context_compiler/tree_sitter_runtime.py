from __future__ import annotations

from functools import lru_cache

from tree_sitter import Parser, Tree
from tree_sitter_language_pack import get_parser


@lru_cache(maxsize=None)
def _parser(language: str) -> Parser:
    return get_parser(language)


def parse_source(language: str, source: bytes) -> Tree:
    return _parser(language).parse(source)


def node_text(source: bytes, node) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")
