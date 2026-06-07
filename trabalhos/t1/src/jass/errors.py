"""Error types and diagnostic formatting for the jass compiler.

The compiler distinguishes three error categories — lexical, syntactic and
semantic — each carrying a source location so diagnostics can point at the exact
spot in the ``.jass`` file. ``format_diagnostic`` renders an error against the
original source with a caret underline, in the familiar ``file:line:col`` style.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Location:
    """A position (and span) in a source file, 1-based line and column."""

    line: int
    column: int
    length: int = 1


class JassError(Exception):
    """Base class for all jass compilation errors.

    Carries an optional :class:`Location`. The ``category`` label is what the
    error reports are grouped under (lexical / syntactic / semantic).
    """

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
    """Render an error as a human-readable, line/col-anchored diagnostic."""

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
