from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Location:
    line: int
    column: int
    length: int = 1


class JassError(Exception):
    category = "compilation"

    def __init__(self, message: str, location: Location | None = None):
        super().__init__(message)
        self.message = message
        self.location = location


class LexicalError(JassError):
    category = "lexical"


class SyntacticError(JassError):
    category = "syntactic"


class SemanticError(JassError):
    category = "semantic"


def format_diagnostic(
    error: JassError, source: str | None = None, filename: str | None = None
) -> str:
    where = filename or "<input>"
    loc = error.location
    
    if loc is not None:
        where = f"{where}:{loc.line}:{loc.column}"

    header = f"{where}: {error.category} error: {error.message}"
    
    if loc is None or source is None:
        return header

    lines = source.splitlines()
    
    if not (1 <= loc.line <= len(lines)):
        return header

    src_line = lines[loc.line - 1]
    caret = " " * (loc.column - 1) + "^" * max(1, loc.length)
    
    return f"{header}\n  {src_line}\n  {caret}"
