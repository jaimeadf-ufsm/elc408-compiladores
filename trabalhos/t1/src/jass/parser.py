"""Lark front-end for jass: lexing and parsing.

Lexing (:func:`tokenize`) maps a bad character to a :class:`LexicalError`.
Parsing (:func:`parse`) runs an LALR(1) parser with panic-mode recovery so a
single run collects *all* syntactic errors instead of stopping at the first: on
an unexpected token it records the error, skips to the next top-level boundary
(`automation`/`def`) and resumes. Unexpected tokens / end-of-input become
:class:`SyntacticError`s with a location.

Tokens are pre-lexed with the basic lexer and fed into the interactive parser;
because keywords are explicit terminals, basic and contextual lexing agree for
this grammar, and feeding tokens ourselves gives full control over recovery.
"""

from __future__ import annotations

from functools import cache
from importlib.resources import files

from lark import Lark, Token, Tree
from lark.exceptions import UnexpectedCharacters, UnexpectedEOF, UnexpectedToken
from lark.lexer import PatternStr

from .errors import LexicalError, Location, SyntacticError

# Top-level boundaries the parser resynchronizes to after a syntactic error.
_SYNC_TOKENS = {"AUTOMATION", "DEF"}

# Human-readable names for the regex terminals, used in "expected ..." messages.
# Keyword/punctuation terminals are described by their literal (see _describe).
_TERMINAL_NAMES = {
    "STRING": "a string",
    "NUMBER": "a number",
    "ENTITY": "an entity reference",
    "NAME": "a name",
    "DURATION": "a duration",
    "TIME": "a time literal",
    "$END": "end of input",
}


def _grammar_source() -> str:
    return files(__package__).joinpath("grammar.lark").read_text(encoding="utf-8")


@cache
def _lexer() -> Lark:
    """A lexer-only Lark instance built from the grammar's terminals."""
    return Lark(_grammar_source(), parser=None, lexer="basic")


@cache
def _parser() -> Lark:
    """The LALR(1) parser used to build parse trees."""
    return Lark(
        _grammar_source(),
        parser="lalr",
        lexer="contextual",
        start="start",
        propagate_positions=True,
    )


def tokenize(source: str) -> list[Token]:
    """Lex ``source`` into a list of tokens, or raise :class:`LexicalError`."""
    try:
        return list(_lexer().lex(source))
    except UnexpectedCharacters as exc:
        location = Location(line=exc.line, column=exc.column)
        char = source[exc.pos_in_stream] if exc.pos_in_stream < len(source) else "?"
        raise LexicalError(f"unexpected character {char!r}", location) from exc


@cache
def _literal_terminals() -> dict[str, str]:
    """Map keyword/punctuation terminal names to their literal text."""
    return {
        term.name: term.pattern.value
        for term in _parser().terminals
        if isinstance(term.pattern, PatternStr)
    }


def _describe(terminal: str) -> str:
    if terminal in _TERMINAL_NAMES:
        return _TERMINAL_NAMES[terminal]
    literal = _literal_terminals().get(terminal)
    return repr(literal) if literal is not None else repr(terminal)


def _expected_clause(expected: set[str]) -> str:
    if not expected:
        return ""
    names = sorted(_describe(t) for t in expected)
    shown = names if len(names) <= 4 else names[:4] + ["..."]
    return f"; expected {', '.join(shown)}"


def _token_error(token: Token, expected: set[str]) -> SyntacticError:
    location = Location(token.line, token.column, length=len(token))
    return SyntacticError(f"unexpected {str(token)!r}{_expected_clause(expected)}", location)


def parse(source: str) -> tuple[Tree | None, list[SyntacticError]]:
    """Parse ``source`` into a parse tree and a list of syntactic errors.

    Returns the tree only when there are no errors; otherwise the (partial)
    tree is discarded and the collected errors are returned for reporting.
    May raise :class:`LexicalError` from the lexing stage.
    """
    tokens = tokenize(source)
    errors: list[SyntacticError] = []

    interactive = _parser().parse_interactive(start="start")
    top_level = interactive.copy()  # snapshot of the empty top-level state

    index = 0
    while index < len(tokens):
        token = tokens[index]
        try:
            interactive.feed_token(token)
            index += 1
        except UnexpectedToken as exc:
            errors.append(_token_error(token, exc.expected))
            # Panic-mode: drop the offending token, skip to the next top-level
            # boundary, and resume parsing from a fresh top-level state.
            index += 1
            while index < len(tokens) and tokens[index].type not in _SYNC_TOKENS:
                index += 1
            interactive = top_level.copy()

    if errors:
        return None, errors

    try:
        return interactive.feed_eof(), errors
    except (UnexpectedToken, UnexpectedEOF) as exc:
        expected = getattr(exc, "expected", set()) or set()
        location = Location(getattr(exc, "line", 1), getattr(exc, "column", 1))
        errors.append(SyntacticError(f"unexpected end of input{_expected_clause(expected)}", location))
        return None, errors
