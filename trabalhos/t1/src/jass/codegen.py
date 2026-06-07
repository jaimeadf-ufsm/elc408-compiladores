"""Lower the jass AST to Home Assistant automation YAML.

Each automation becomes a plain dict in HA shape (``alias``, ``mode``,
``triggers``, ``conditions?``, ``actions``); the whole file becomes a YAML list.
Aliases are resolved to their bound values here — nothing about ``def`` survives
into the YAML. Actions lower per their :mod:`registry` definition, routing each
argument to the right HA field and converting its value by type. The result is
dumped with ``ruamel.yaml`` in block style with quoted string scalars.
"""

from __future__ import annotations

import io

from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import DoubleQuotedScalarString as Quoted

from . import ast, registry


def _q(text: str) -> Quoted:
    return Quoted(text)


class CodeGen:
    def __init__(self) -> None:
        self.scopes: list[dict[str, ast.Value]] = []

    # ----- scopes & alias resolution -----

    def resolve(self, value: ast.Value) -> ast.Value:
        """Follow alias references to the concrete value they stand for."""
        while isinstance(value, ast.AliasRef):
            for scope in reversed(self.scopes):
                if value.name in scope:
                    value = scope[value.name]
                    break
            else:  # pragma: no cover - guaranteed bound by the analyzer
                break
        return value

    # ----- program & automations -----

    def generate(self, program: ast.Program) -> list[dict]:
        self.scopes = [{}]
        automations = []
        for item in program.items:
            if isinstance(item, ast.DefBinding):
                self.scopes[-1][item.name] = item.value
            else:
                automations.append(self.gen_automation(item))
        return automations

    def gen_automation(self, automation: ast.Automation) -> dict:
        meta = {entry.key: entry.value for entry in automation.metadata}
        result: dict = {}
        result["alias"] = _q(automation.name or "")
        if "description" in meta:
            result["description"] = _q(self.resolve(meta["description"]).value)
        result["mode"] = _q(meta["mode"].value if "mode" in meta else "single")
        if "max" in meta:
            result["max"] = meta["max"].value

        result["triggers"] = [self.gen_trigger(t) for t in automation.triggers]
        if automation.condition is not None:
            result["conditions"] = self.conditions_of(automation.condition)
        result["actions"] = self.gen_block(automation.body)
        return result

    # ----- triggers -----

    def gen_trigger(self, trigger: ast.Trigger) -> dict:
        result: dict = {}
        if isinstance(trigger, ast.StateTrigger):
            result["trigger"] = "state"
            result["entity_id"] = self.entity_id(trigger.entity)
            if trigger.from_value is not None:
                result["from"] = self.lower(trigger.from_value)
            if trigger.to_value is not None:
                result["to"] = self.lower(trigger.to_value)
            if trigger.for_duration is not None:
                result["for"] = _q(trigger.for_duration.value.as_hms())
        elif isinstance(trigger, ast.NumericTrigger):
            result["trigger"] = "numeric_state"
            result["entity_id"] = self.entity_id(trigger.entity)
            result["above" if trigger.op == ">" else "below"] = self.lower(trigger.threshold)
            if trigger.for_duration is not None:
                result["for"] = _q(trigger.for_duration.value.as_hms())
        elif isinstance(trigger, ast.TimeTrigger):
            result["trigger"] = "time"
            result["at"] = _q(trigger.time.as_hms())
        elif isinstance(trigger, ast.SunTrigger):
            result["trigger"] = "sun"
            result["event"] = trigger.event
            if trigger.offset is not None:
                result["offset"] = _q(self.signed_offset(trigger.offset_sign, trigger.offset))
        if trigger.id is not None:
            result["id"] = _q(trigger.id)
        return result

    # ----- conditions -----

    def conditions_of(self, condition: ast.BoolExpr) -> list[dict]:
        """A condition list (implicitly AND-ed), flattening a top-level ``and``."""
        if isinstance(condition, ast.And):
            return [self.gen_condition(op) for op in condition.operands]
        return [self.gen_condition(condition)]

    def gen_condition(self, expr: ast.BoolExpr) -> dict:
        if isinstance(expr, ast.Or):
            return {"or": [self.gen_condition(op) for op in expr.operands]}
        if isinstance(expr, ast.And):
            return {"and": [self.gen_condition(op) for op in expr.operands]}
        if isinstance(expr, ast.Not):
            return {"not": [self.gen_condition(expr.operand)]}
        if isinstance(expr, ast.StateCondition):
            state = {"condition": "state", "entity_id": self.entity_id(expr.entity), "state": self.lower(expr.value)}
            return state if expr.op == "==" else {"not": [state]}
        if isinstance(expr, ast.NumericCondition):
            key = "above" if expr.op == ">" else "below"
            return {"condition": "numeric_state", "entity_id": self.entity_id(expr.entity), key: self.lower(expr.threshold)}
        if isinstance(expr, ast.TimeCondition):
            return {"condition": "time", expr.op: _q(expr.time.as_hms())}
        if isinstance(expr, ast.DayCondition):
            return {"condition": "time", "weekday": [_q(day) for day in expr.days]}
        if isinstance(expr, ast.SunCondition):
            result = {"condition": "sun", expr.op: expr.event}
            if expr.offset is not None:
                result[f"{expr.op}_offset"] = _q(self.signed_offset(expr.offset_sign, expr.offset))
            return result
        if isinstance(expr, ast.TriggeredBy):
            return {"condition": "trigger", "id": _q(expr.id)}
        raise AssertionError(f"unhandled condition {type(expr).__name__}")

    # ----- statements -----

    def gen_block(self, statements: list[ast.Statement]) -> list[dict]:
        self.scopes.append({})
        actions = []
        for statement in statements:
            if isinstance(statement, ast.DefBinding):
                self.scopes[-1][statement.name] = statement.value
            elif isinstance(statement, ast.ActionCall):
                actions.append(self.gen_action(statement))
            elif isinstance(statement, ast.IfStatement):
                actions.append(self.gen_if(statement.branches, statement.else_body))
            elif isinstance(statement, ast.SafeBlock):
                actions.append(self.gen_safe(statement))
        self.scopes.pop()
        return actions

    def gen_if(self, branches: list[ast.ConditionalBranch], else_body: list[ast.Statement] | None) -> dict:
        first, rest = branches[0], branches[1:]
        node: dict = {"if": self.conditions_of(first.condition), "then": self.gen_block(first.body)}
        if rest:
            node["else"] = [self.gen_if(rest, else_body)]  # elif chains nest in else
        elif else_body is not None:
            node["else"] = self.gen_block(else_body)
        return node

    def gen_safe(self, safe: ast.SafeBlock) -> dict:
        children = self.gen_block(safe.body)
        for child in children:
            child["continue_on_error"] = True
        return {"sequence": children}

    def gen_action(self, call: ast.ActionCall) -> dict:
        special = registry.special_action(call.name)
        if special is not None and special.kind == "delay":
            duration = self.resolve(self.bind(call, special)["duration"])
            return {"delay": _q(duration.value.as_hms())}
        if special is not None and special.kind == "call":
            return self.gen_call(call)

        domain = self.primary_domain(call)
        action = registry.domain_action(call.name, domain)
        return self.gen_service(call, action)

    def gen_service(self, call: ast.ActionCall, action: registry.ActionDef) -> dict:
        bound = self.bind(call, action)
        result: dict = {"action": action.service}
        data: dict = {}
        for param in action.params:
            if param.name not in bound:
                continue
            value = bound[param.name]
            if param.field == "target":
                result["target"] = {"entity_id": self.entity_id(value)}
            else:
                data[param.field] = self.lower_arg(param, value)
        if data:
            result["data"] = data
        return result

    def gen_call(self, call: ast.ActionCall) -> dict:
        bound = self.bind(call, registry.special_action("call"))
        result: dict = {"action": self.lower(bound["service"])}
        if "target" in bound:
            result["target"] = {"entity_id": self.entity_id(bound["target"])}
        if "data" in bound:
            result["data"] = self.lower(bound["data"])
        return result

    # ----- argument binding & value lowering -----

    def bind(self, call: ast.ActionCall, action: registry.ActionDef) -> dict[str, ast.Value]:
        """Bind positional (by order) and named arguments to parameter names."""
        bound: dict[str, ast.Value] = {}
        for param, value in zip(action.params, call.positional):
            bound[param.name] = value
        for arg in call.named:
            bound[arg.name] = arg.value
        return bound

    def lower_arg(self, param: registry.Param, value: ast.Value):
        value = self.resolve(value)
        if param.type == "duration":
            duration = value.value
            return duration.total_seconds if param.field == "transition" else _q(duration.as_hms())
        if param.type == "color":
            return value.value.as_list()
        return self.lower(value)

    def entity_id(self, value: ast.Value):
        """Render an entity target: a single id or a list of ids."""
        value = self.resolve(value)
        if isinstance(value, ast.ListLit):
            return [str(self.resolve(item).value) for item in value.items]
        return str(value.value)

    def lower(self, value: ast.Value):
        value = self.resolve(value)
        if isinstance(value, ast.String):
            return _q(value.value)
        if isinstance(value, (ast.Number, ast.Boolean)):
            return value.value
        if isinstance(value, ast.DurationLit):
            return _q(value.value.as_hms())
        if isinstance(value, ast.TimeLit):
            return _q(value.value.as_hms())
        if isinstance(value, ast.ColorLit):
            return value.value.as_list()
        if isinstance(value, ast.EntityLit):
            return str(value.value)
        if isinstance(value, ast.ListLit):
            return [self.lower(item) for item in value.items]
        if isinstance(value, ast.DictLit):
            return {key: self.lower(item) for key, item in value.pairs}
        raise AssertionError(f"unhandled value {type(value).__name__}")

    # ----- helpers -----

    def primary_domain(self, call: ast.ActionCall) -> str:
        primary = call.positional[0] if call.positional else next(a.value for a in call.named if a.name == "target")
        primary = self.resolve(primary)
        if isinstance(primary, ast.ListLit):
            primary = self.resolve(primary.items[0])
        return primary.value.domain

    def signed_offset(self, sign: str | None, duration) -> str:
        prefix = "-" if sign == "-" else ""
        return f"{prefix}{duration.as_hms()}"


def generate(program: ast.Program) -> list[dict]:
    return CodeGen().generate(program)


def dump(program: ast.Program) -> str:
    """Generate HA YAML for ``program`` and return it as a string."""
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.indent(mapping=2, sequence=4, offset=2)
    stream = io.StringIO()
    yaml.dump(generate(program), stream)
    return stream.getvalue().rstrip("\n")
