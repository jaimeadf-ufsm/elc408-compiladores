"""Typed AST for jass.

Every node carries an optional source :class:`Location` (keyword-only, so it
never interferes with positional fields) for diagnostics. The tree splits into
values (expressions), triggers, boolean-condition expressions, and statements.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

from .errors import Location
from .values import Color, Duration, EntityRef, TimeOfDay


@dataclass
class Node:
    location: Location | None = field(default=None, kw_only=True)


# ----- values -----


@dataclass
class Value(Node):
    """Base for expression/value nodes."""


@dataclass
class String(Value):
    value: str


@dataclass
class Number(Value):
    value: int | float


@dataclass
class Boolean(Value):
    value: bool


@dataclass
class DurationLit(Value):
    value: Duration


@dataclass
class TimeLit(Value):
    value: TimeOfDay


@dataclass
class ColorLit(Value):
    value: Color


@dataclass
class EntityLit(Value):
    """A direct entity reference, e.g. ``light.living_room``."""

    value: EntityRef


@dataclass
class AliasRef(Value):
    """A reference to a ``def`` alias, resolved during analysis."""

    name: str


@dataclass
class ListLit(Value):
    items: list[Value]


@dataclass
class DictLit(Value):
    pairs: list[tuple[str, Value]]


# An entity position accepts a direct reference or an alias standing in for one.
EntityExpr = EntityLit | AliasRef


# ----- triggers -----


@dataclass
class Trigger(Node):
    id: str | None = field(default=None, kw_only=True)


@dataclass
class StateTrigger(Trigger):
    entity: EntityExpr
    from_value: Value | None = None
    to_value: Value | None = None
    for_duration: DurationLit | None = None


@dataclass
class NumericTrigger(Trigger):
    entity: EntityExpr
    op: str  # "<" or ">"
    threshold: Value
    for_duration: DurationLit | None = None


@dataclass
class TimeTrigger(Trigger):
    time: TimeOfDay


@dataclass
class SunTrigger(Trigger):
    event: str  # "sunset" or "sunrise"
    offset: Duration | None = None
    offset_sign: str | None = None  # "+" or "-"


# ----- conditions (boolean expressions) -----


@dataclass
class BoolExpr(Node):
    """Base for condition expressions."""


@dataclass
class Or(BoolExpr):
    operands: list[BoolExpr]


@dataclass
class And(BoolExpr):
    operands: list[BoolExpr]


@dataclass
class Not(BoolExpr):
    operand: BoolExpr


@dataclass
class StateCondition(BoolExpr):
    entity: EntityExpr
    op: str  # "==" or "!="
    value: Value


@dataclass
class NumericCondition(BoolExpr):
    entity: EntityExpr
    op: str  # "<" or ">"
    threshold: Value


@dataclass
class TimeCondition(BoolExpr):
    op: str  # "after" or "before"
    time: TimeOfDay


@dataclass
class DayCondition(BoolExpr):
    days: list[str]


@dataclass
class SunCondition(BoolExpr):
    op: str  # "after" or "before"
    event: str  # "sunset" or "sunrise"
    offset: Duration | None = None
    offset_sign: str | None = None


@dataclass
class TriggeredBy(BoolExpr):
    id: str


# ----- statements -----


@dataclass
class Statement(Node):
    """Base for statements in a do/if/safe block."""


@dataclass
class NamedArg(Node):
    name: str
    value: Value


@dataclass
class ActionCall(Statement):
    name: str
    positional: list[Value]
    named: list[NamedArg]


@dataclass
class ConditionalBranch(Node):
    """An ``if``/``elif`` arm: a condition and the body it guards."""

    condition: BoolExpr
    body: list[Statement]


@dataclass
class IfStatement(Statement):
    branches: list[ConditionalBranch]
    else_body: list[Statement] | None = None


@dataclass
class SafeBlock(Statement):
    body: list[Statement]


@dataclass
class DefBinding(Statement):
    """A ``def NAME = value`` alias binding (file-level or block-level)."""

    name: str
    value: Value


# ----- top level -----


@dataclass
class Metadata(Node):
    key: str
    value: Value


@dataclass
class Automation(Node):
    name: str | None
    metadata: list[Metadata]
    triggers: list[Trigger]
    condition: BoolExpr | None
    body: list[Statement]


@dataclass
class Program(Node):
    items: list[Automation | DefBinding]


def dump(value, indent: int = 0) -> str:
    """Render an AST node (or any of its field values) as indented text."""
    pad = "  " * (indent + 1)
    if isinstance(value, Node):
        fields = [f for f in dataclasses.fields(value) if f.name != "location"]
        rendered = [type(value).__name__]
        for f in fields:
            child = getattr(value, f.name)
            rendered.append(f"{pad}{f.name}: {dump(child, indent + 1)}")
        return "\n".join(rendered)
    if isinstance(value, list):
        if not value:
            return "[]"
        return "\n" + "\n".join(f"{pad}- {dump(item, indent + 1)}" for item in value)
    if isinstance(value, tuple):
        return "(" + ", ".join(dump(item, indent) for item in value) + ")"
    if isinstance(value, str):
        return repr(value)
    return str(value)
