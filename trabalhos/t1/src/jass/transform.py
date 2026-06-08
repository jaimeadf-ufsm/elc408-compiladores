"""Lower a Lark parse tree to the typed jass AST.

A bottom-up :class:`lark.Transformer` builds the AST defined in :mod:`ast`,
attaching a source :class:`Location` (from propagated positions) to every node.
Rules marked ``?`` in the grammar inline their single child, so this only needs
methods for the nodes it actually constructs.
"""

from __future__ import annotations

import re

from lark import Token, Tree, v_args
from lark.visitors import Transformer

from . import ast
from .errors import Location
from .values import Color, Duration, EntityRef, TimeOfDay

# Internal carriers used to disambiguate same-shaped children (e.g. the trigger
# list vs the action body, which are both plain Python lists) while assembling an
# automation or an if-statement. They never escape this module.


class _Carrier:
    def __init__(self, items: list):
        self.items = items


class _Triggers(_Carrier):
    pass


class _Body(_Carrier):
    pass


class _Else(_Carrier):
    pass


def _loc(meta) -> Location | None:
    if meta is None or meta.empty:
        return None
    length = 1
    if meta.end_line == meta.line and meta.end_column > meta.column:
        length = meta.end_column - meta.column
    return Location(meta.line, meta.column, length)


def _unquote(token: Token) -> str:
    escapes = {"n": "\n", "t": "\t", "r": "\r"}
    body = str(token)[1:-1]
    return re.sub(r"\\(.)", lambda m: escapes.get(m.group(1), m.group(1)), body)


def _token(children, type_: str) -> Token | None:
    for child in children:
        if isinstance(child, Token) and child.type == type_:
            return child
    return None


def _op(children, *types: str) -> str:
    for child in children:
        if isinstance(child, Token) and child.type in types:
            return str(child)
    raise AssertionError(f"expected one of {types} in {children}")


@v_args(meta=True)
class AstBuilder(Transformer):
    # ----- values -----

    def string(self, meta, children):
        return ast.String(_unquote(children[0]), location=_loc(meta))

    def number(self, meta, children):
        text = str(children[0])
        value = float(text) if "." in text else int(text)
        return ast.Number(value, location=_loc(meta))

    def true(self, meta, children):
        return ast.Boolean(True, location=_loc(meta))

    def false(self, meta, children):
        return ast.Boolean(False, location=_loc(meta))

    def duration(self, meta, children):
        return ast.DurationLit(Duration.parse(str(children[0])), location=_loc(meta))

    def time_value(self, meta, children):
        return ast.TimeLit(TimeOfDay.parse(str(children[0])), location=_loc(meta))

    def entity_ref(self, meta, children):
        return ast.EntityLit(EntityRef.parse(str(children[0])), location=_loc(meta))

    def alias_ref(self, meta, children):
        return ast.AliasRef(str(children[0]), location=_loc(meta))

    def list(self, meta, children):
        items = [c for c in children if isinstance(c, ast.Value)]
        return ast.ListLit(items, location=_loc(meta))

    def pair(self, meta, children):
        return (_unquote(children[0]), children[-1])

    def dict(self, meta, children):
        pairs = [c for c in children if isinstance(c, tuple)]
        return ast.DictLit(pairs, location=_loc(meta))

    def color(self, meta, children):
        r, g, b = (int(str(c)) for c in children if isinstance(c, Token) and c.type == "NUMBER")
        return ast.ColorLit(Color(r, g, b), location=_loc(meta))

    # ----- triggers -----

    def when_block(self, meta, children):
        return _Triggers([c for c in children if isinstance(c, ast.Trigger)])

    def trigger(self, meta, children):
        trig = next(c for c in children if isinstance(c, ast.Trigger))
        label = _token(children, "STRING")
        if label is not None:
            trig.id = _unquote(label)
        return trig

    def state_trigger(self, meta, children):
        entity = children[0]
        from_value = to_value = for_duration = None
        index = 1
        while index < len(children):
            child = children[index]
            if isinstance(child, Token) and child.type == "FROM":
                from_value = children[index + 1]
                index += 2
            elif isinstance(child, Token) and child.type == "TO":
                to_value = children[index + 1]
                index += 2
            elif isinstance(child, Token) and child.type == "FOR":
                for_duration = ast.DurationLit(Duration.parse(str(children[index + 1])))
                index += 2
            else:
                index += 1
        return ast.StateTrigger(entity, from_value, to_value, for_duration, location=_loc(meta))

    def numeric_trigger(self, meta, children):
        entity = children[0]
        op = _op(children, "LT", "GT")
        threshold = next(c for c in children[1:] if isinstance(c, ast.Value))
        for_token = _token(children, "DURATION")
        for_duration = ast.DurationLit(Duration.parse(str(for_token))) if for_token else None
        return ast.NumericTrigger(entity, op, threshold, for_duration, location=_loc(meta))

    def time_trigger(self, meta, children):
        return ast.TimeTrigger(TimeOfDay.parse(str(children[0])), location=_loc(meta))

    def sun_trigger(self, meta, children):
        return ast.SunTrigger(children[0], location=_loc(meta))

    def sun_event(self, meta, children):
        event = _op(children, "SUNSET", "SUNRISE")
        sign = _op(children, "PLUS", "MINUS") if _token(children, "PLUS") or _token(children, "MINUS") else None
        offset_token = _token(children, "DURATION")
        offset = Duration.parse(str(offset_token)) if offset_token else None
        return ast.SunPoint(event, offset, sign, location=_loc(meta))

    # ----- conditions -----

    def condition_block(self, meta, children):
        return next(c for c in children if isinstance(c, ast.BoolExpr))

    def atom(self, meta, children):
        # A parenthesized boolean expression: ( bool_expr ).
        return next(c for c in children if isinstance(c, ast.BoolExpr))

    def or_expr(self, meta, children):
        return ast.Or([c for c in children if isinstance(c, ast.BoolExpr)], location=_loc(meta))

    def and_expr(self, meta, children):
        return ast.And([c for c in children if isinstance(c, ast.BoolExpr)], location=_loc(meta))

    def not_expr(self, meta, children):
        operand = next(c for c in children if isinstance(c, ast.BoolExpr))
        return ast.Not(operand, location=_loc(meta))

    def state_condition(self, meta, children):
        entity = children[0]
        op = _op(children, "EQ", "NE")
        value = next(c for c in children[1:] if isinstance(c, ast.Value))
        return ast.StateCondition(entity, op, value, location=_loc(meta))

    def numeric_condition(self, meta, children):
        entity = children[0]
        op = _op(children, "LT", "GT")
        threshold = next(c for c in children[1:] if isinstance(c, ast.Value))
        return ast.NumericCondition(entity, op, threshold, location=_loc(meta))

    def time_condition(self, meta, children):
        times = [TimeOfDay.parse(str(c)) for c in children if isinstance(c, Token) and c.type == "TIME"]
        after, before = self._window(children, times)
        return ast.TimeCondition(after, before, location=_loc(meta))

    def day_condition(self, meta, children):
        days_list = next(c for c in children if isinstance(c, ast.ListLit))
        days = [item.value for item in days_list.items if isinstance(item, ast.String)]
        return ast.DayCondition(days, location=_loc(meta))

    def sun_condition(self, meta, children):
        points = [c for c in children if isinstance(c, ast.SunPoint)]
        after, before = self._window(children, points)
        return ast.SunCondition(after, before, location=_loc(meta))

    @staticmethod
    def _window(children, bounds):
        """Split bounds into (after, before) by the after/before/between keyword."""
        if _token(children, "BETWEEN"):
            return bounds[0], bounds[1]
        if _token(children, "AFTER"):
            return bounds[0], None
        return None, bounds[0]

    def triggeredby_condition(self, meta, children):
        return ast.TriggeredBy(_unquote(_token(children, "STRING")), location=_loc(meta))

    # ----- statements -----

    def block(self, meta, children):
        return [c for c in children if isinstance(c, ast.Statement)]

    def do_block(self, meta, children):
        return _Body(next(c for c in children if isinstance(c, list)))

    def named_arg(self, meta, children):
        name = str(_token(children, "NAME"))
        value = next(c for c in children if isinstance(c, ast.Value))
        return ast.NamedArg(name, value, location=_loc(meta))

    def pos_args(self, meta, children):
        result: list = []
        for child in children:
            if isinstance(child, list):
                result.extend(child)
            elif isinstance(child, ast.Value):
                result.append(child)
        return result

    def kw_args(self, meta, children):
        result: list = []
        for child in children:
            if isinstance(child, list):
                result.extend(child)
            elif isinstance(child, ast.NamedArg):
                result.append(child)
        return result

    def arguments(self, meta, children):
        positional: list = []
        named: list = []
        for child in children:
            if isinstance(child, list) and child:
                if isinstance(child[0], ast.NamedArg):
                    named = child
                else:
                    positional = child
        return (positional, named)

    def action_call(self, meta, children):
        name = str(children[0])
        positional, named = next((c for c in children if isinstance(c, tuple)), ([], []))
        return ast.ActionCall(name, positional, named, location=_loc(meta))

    def elif_clause(self, meta, children):
        condition = next(c for c in children if isinstance(c, ast.BoolExpr))
        body = next(c for c in children if isinstance(c, list))
        return ast.ConditionalBranch(condition, body, location=_loc(meta))

    def else_clause(self, meta, children):
        return _Else(next(c for c in children if isinstance(c, list)))

    def if_statement(self, meta, children):
        condition = then_body = else_body = None
        elifs: list[ast.ConditionalBranch] = []
        for child in children:
            if isinstance(child, ast.BoolExpr) and condition is None:
                condition = child
            elif isinstance(child, list) and then_body is None:
                then_body = child
            elif isinstance(child, ast.ConditionalBranch):
                elifs.append(child)
            elif isinstance(child, _Else):
                else_body = child.items
        branches = [ast.ConditionalBranch(condition, then_body), *elifs]
        return ast.IfStatement(branches, else_body, location=_loc(meta))

    def safe_block(self, meta, children):
        return ast.SafeBlock(next(c for c in children if isinstance(c, list)), location=_loc(meta))

    def def_binding(self, meta, children):
        name = str(_token(children, "NAME"))
        value = next(c for c in children if isinstance(c, ast.Value))
        return ast.DefBinding(name, value, location=_loc(meta))

    # ----- top level -----

    def metadata(self, meta, children):
        key = str(_token(children, "NAME"))
        value = next(c for c in children if isinstance(c, ast.Value))
        return ast.Metadata(key, value, location=_loc(meta))

    def automation(self, meta, children):
        name = None
        metadata: list[ast.Metadata] = []
        triggers: list[ast.Trigger] = []
        condition = None
        body: list[ast.Statement] = []
        for child in children:
            if isinstance(child, Token) and child.type == "STRING":
                name = _unquote(child)
            elif isinstance(child, ast.Metadata):
                metadata.append(child)
            elif isinstance(child, _Triggers):
                triggers = child.items
            elif isinstance(child, _Body):
                body = child.items
            elif isinstance(child, ast.BoolExpr):
                condition = child
        return ast.Automation(name, metadata, triggers, condition, body, location=_loc(meta))

    def start(self, meta, children):
        items = [c for c in children if isinstance(c, (ast.Automation, ast.DefBinding))]
        return ast.Program(items, location=_loc(meta))


def build_ast(tree: Tree) -> ast.Program:
    """Transform a parse tree into a typed :class:`ast.Program`."""
    return AstBuilder().transform(tree)
