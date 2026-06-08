from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

from .errors import Location
from .values import Color, Duration, EntityRef, TimeOfDay


@dataclass
class Node:
    location: Location | None = field(default=None, kw_only=True)


@dataclass
class Value(Node):
    pass


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
    value: EntityRef


@dataclass
class AliasRef(Value):
    name: str


@dataclass
class ListLit(Value):
    items: list[Value]


@dataclass
class DictLit(Value):
    pairs: list[tuple[str, Value]]


EntityExpr = EntityLit | AliasRef


# Triggers

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
class SunPoint(Node):
    event: str  # "sunset" or "sunrise"
    offset: Duration | None = None
    offset_sign: str | None = None  # "+" or "-"


@dataclass
class SunTrigger(Trigger):
    point: SunPoint


# Conditions

@dataclass
class BoolExpr(Node):
    pass


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
    after: TimeOfDay | None = None
    before: TimeOfDay | None = None


@dataclass
class DayCondition(BoolExpr):
    days: list[str]


@dataclass
class SunCondition(BoolExpr):
    after: SunPoint | None = None
    before: SunPoint | None = None


@dataclass
class TriggeredBy(BoolExpr):
    id: str


# Statements

@dataclass
class Statement(Node):
    pass


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
    name: str
    value: Value


# Top-level items

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
