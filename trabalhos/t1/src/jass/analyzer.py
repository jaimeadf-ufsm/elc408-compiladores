"""Semantic analysis for jass — the heavy lifting.

Walks the AST per automation and collects *all* errors (it never fails fast),
maintaining a symbol table over nested scopes (file-global, per-automation,
per-block). It resolves ``def`` aliases (with shadowing) and trigger ids, infers
value types, and enforces the action rules from the curated :mod:`registry`:
target-domain consistency, action↔domain support, and domain-dependent argument
validity/typing. Aliases are resolved to their bound type before any check, so an
alias never relaxes a rule.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import ast, registry
from .errors import Location, SemanticError

_VALID_MODES = {"single", "restart", "queued", "parallel"}
_MODES_WITH_MAX = {"queued", "parallel"}

# Human-readable names for value type kinds, used in diagnostics.
_TYPE_NAMES = {
    "string": "a string",
    "number": "a number",
    "bool": "a boolean",
    "duration": "a duration",
    "time": "a time",
    "color": "a color",
    "entity": "an entity",
    "list": "a list",
    "dict": "a dict",
    "unknown": "an unknown value",
}


@dataclass(frozen=True)
class Type:
    """An inferred value type; ``domain`` is set only for entities."""

    kind: str
    domain: str | None = None


UNKNOWN = Type("unknown")


@dataclass(frozen=True)
class Symbol:
    """A bound ``def`` alias: its inferred type and the value it stands for."""

    type: Type
    value: ast.Value


class Scope:
    """A lexical scope in the symbol-table stack; resolves into its parent."""

    def __init__(self, parent: "Scope | None" = None):
        self.parent = parent
        self.symbols: dict[str, Symbol] = {}

    def define(self, name: str, symbol: Symbol) -> None:
        self.symbols[name] = symbol  # shadows any outer binding of the same name

    def resolve(self, name: str) -> Symbol | None:
        scope: Scope | None = self
        while scope is not None:
            if name in scope.symbols:
                return scope.symbols[name]
            scope = scope.parent
        return None


class Analyzer:
    def __init__(self) -> None:
        self.errors: list[SemanticError] = []
        self.trigger_ids: set[str] = set()

    # ----- error helpers -----

    def error(self, message: str, location: Location | None) -> None:
        self.errors.append(SemanticError(message, location))

    # ----- entry point -----

    def analyze(self, program: ast.Program) -> list[SemanticError]:
        global_scope = Scope()
        for item in program.items:
            if isinstance(item, ast.DefBinding):
                self.bind_def(item, global_scope)
            else:
                self.analyze_automation(item, global_scope)
        return self.errors

    # ----- aliases & type inference -----

    def bind_def(self, binding: ast.DefBinding, scope: Scope) -> None:
        type_ = self.infer(binding.value, scope)
        scope.define(binding.name, Symbol(type_, binding.value))

    def infer(self, value: ast.Value, scope: Scope) -> Type:
        """Infer a value's type, reporting undeclared/out-of-scope aliases."""
        if isinstance(value, ast.String):
            return Type("string")
        if isinstance(value, ast.Number):
            return Type("number")
        if isinstance(value, ast.Boolean):
            return Type("bool")
        if isinstance(value, ast.DurationLit):
            return Type("duration")
        if isinstance(value, ast.TimeLit):
            return Type("time")
        if isinstance(value, ast.ColorLit):
            return Type("color")
        if isinstance(value, ast.EntityLit):
            return Type("entity", value.value.domain)
        if isinstance(value, ast.ListLit):
            for item in value.items:
                self.infer(item, scope)
            return Type("list")
        if isinstance(value, ast.DictLit):
            for _, item in value.pairs:
                self.infer(item, scope)
            return Type("dict")
        if isinstance(value, ast.AliasRef):
            symbol = scope.resolve(value.name)
            if symbol is None:
                self.error(f"undeclared name {value.name!r}", value.location)
                return UNKNOWN
            return symbol.type
        return UNKNOWN

    # ----- automations -----

    def analyze_automation(self, automation: ast.Automation, global_scope: Scope) -> None:
        scope = Scope(global_scope)
        self.trigger_ids = {t.id for t in automation.triggers if t.id is not None}

        self.check_metadata(automation.metadata)
        for trigger in automation.triggers:
            self.analyze_trigger(trigger, scope)
        if automation.condition is not None:
            self.analyze_bool(automation.condition, scope)
        self.analyze_block(automation.body, scope)

    def check_metadata(self, metadata: list[ast.Metadata]) -> None:
        seen: dict[str, ast.Value] = {}
        for entry in metadata:
            seen[entry.key] = entry.value
            if entry.key == "description":
                if not isinstance(entry.value, ast.String):
                    self.error("'description' must be a string", entry.location)
            elif entry.key == "mode":
                if not (isinstance(entry.value, ast.String) and entry.value.value in _VALID_MODES):
                    modes = ", ".join(sorted(_VALID_MODES))
                    self.error(f"'mode' must be one of: {modes}", entry.location)
            elif entry.key == "max":
                if not (isinstance(entry.value, ast.Number) and isinstance(entry.value.value, int)):
                    self.error("'max' must be an integer", entry.location)
            else:
                self.error(f"unknown metadata {entry.key!r}", entry.location)
        if "max" in seen:
            mode = seen.get("mode")
            mode_value = mode.value if isinstance(mode, ast.String) else None
            if mode_value not in _MODES_WITH_MAX:
                self.error("'max' is only allowed with mode 'queued' or 'parallel'", seen["max"].location)

    # ----- triggers -----

    def analyze_trigger(self, trigger: ast.Trigger, scope: Scope) -> None:
        if isinstance(trigger, ast.StateTrigger):
            self.resolve_entity(trigger.entity, scope)
            for value in (trigger.from_value, trigger.to_value):
                if value is not None:
                    self.infer(value, scope)
        elif isinstance(trigger, ast.NumericTrigger):
            self.resolve_entity(trigger.entity, scope)
            self.expect(trigger.threshold, "number", scope, "numeric threshold")

    # ----- conditions -----

    def analyze_bool(self, expr: ast.BoolExpr, scope: Scope) -> None:
        if isinstance(expr, ast.Or):
            for operand in expr.operands:
                self.analyze_bool(operand, scope)
        elif isinstance(expr, ast.And):
            for operand in expr.operands:
                self.analyze_bool(operand, scope)
        elif isinstance(expr, ast.Not):
            self.analyze_bool(expr.operand, scope)
        elif isinstance(expr, ast.StateCondition):
            self.resolve_entity(expr.entity, scope)
            self.infer(expr.value, scope)
        elif isinstance(expr, ast.NumericCondition):
            self.resolve_entity(expr.entity, scope)
            self.expect(expr.threshold, "number", scope, "numeric threshold")
        elif isinstance(expr, ast.TriggeredBy):
            if expr.id not in self.trigger_ids:
                self.error(f"trigger id {expr.id!r} is never declared", expr.location)

    # ----- statements -----

    def analyze_block(self, statements: list[ast.Statement], parent: Scope) -> None:
        scope = Scope(parent)
        for statement in statements:
            if isinstance(statement, ast.DefBinding):
                self.bind_def(statement, scope)
            elif isinstance(statement, ast.ActionCall):
                self.analyze_action(statement, scope)
            elif isinstance(statement, ast.IfStatement):
                for branch in statement.branches:
                    self.analyze_bool(branch.condition, scope)
                    self.analyze_block(branch.body, scope)
                if statement.else_body is not None:
                    self.analyze_block(statement.else_body, scope)
            elif isinstance(statement, ast.SafeBlock):
                self.analyze_block(statement.body, scope)

    # ----- actions -----

    def analyze_action(self, call: ast.ActionCall, scope: Scope) -> None:
        special = registry.special_action(call.name)
        if special is not None and special.kind == "call":
            # call(): blind passthrough — exempt from validation, but still
            # resolve aliases so undeclared names are caught.
            for value in call.positional:
                self.infer(value, scope)
            for arg in call.named:
                self.infer(arg.value, scope)
            return
        if special is not None:
            self.check_arguments(call, special, scope, primary_checked=False)
            return

        if not registry.is_known_action(call.name):
            self.error(f"unknown action {call.name!r}", call.location)
            return

        domain = self.action_domain(call, scope)
        if domain is None:
            return  # primary missing or inconsistent — already reported

        action = registry.domain_action(call.name, domain)
        if action is None:
            supported = ", ".join(sorted(registry.action_domains(call.name)))
            self.error(
                f"action {call.name!r} does not support domain {domain!r} (supported: {supported})",
                call.location,
            )
            return

        # action_domain already inferred/checked the primary (the target entity).
        self.check_arguments(call, action, scope, primary_checked=True)

    def action_domain(self, call: ast.ActionCall, scope: Scope) -> str | None:
        """The target domain of a domain-based action, or None if unresolvable."""
        primary = self.primary_value(call)
        if primary is None:
            self.error(f"action {call.name!r} requires a target entity", call.location)
            return None

        if isinstance(primary, ast.ListLit):
            domains = {self.entity_domain(item, scope) for item in primary.items}
            domains.discard(None)
            if len(domains) > 1:
                listed = ", ".join(sorted(d for d in domains if d))
                self.error(f"all entities in a target list must share one domain (found: {listed})", primary.location)
                return None
            return next(iter(domains), None)

        return self.entity_domain(primary, scope)

    def primary_value(self, call: ast.ActionCall) -> ast.Value | None:
        if call.positional:
            return call.positional[0]
        return next((arg.value for arg in call.named if arg.name == "target"), None)

    def entity_domain(self, value: ast.Value, scope: Scope) -> str | None:
        type_ = self.infer(value, scope)
        if type_.kind == "unknown":
            return None  # undeclared alias already reported; avoid cascading
        if type_.kind != "entity":
            self.error(f"expected an entity, got {_TYPE_NAMES.get(type_.kind, type_.kind)}", value.location)
            return None
        return type_.domain

    def check_arguments(
        self, call: ast.ActionCall, action: registry.ActionDef, scope: Scope, primary_checked: bool
    ) -> None:
        bound: dict[str, ast.Value] = {}

        # Positional args bind to parameters in order; extra ones are resolved
        # (to catch undeclared aliases) and reported as too many.
        if len(call.positional) > len(action.params):
            self.error(
                f"action {call.name!r} takes at most {len(action.params)} positional argument(s), "
                f"got {len(call.positional)}",
                call.location,
            )
        for index, value in enumerate(call.positional):
            if index < len(action.params):
                bound[action.params[index].name] = value
            else:
                self.infer(value, scope)

        # Named args bind by name; reject unknown and duplicate.
        for arg in call.named:
            param = action.param(arg.name)
            if param is None:
                self.error(f"action {call.name!r} has no argument {arg.name!r}", arg.location)
                self.infer(arg.value, scope)
            elif param.name in bound:
                self.error(f"argument {arg.name!r} given more than once", arg.location)
                self.infer(arg.value, scope)
            else:
                bound[param.name] = arg.value

        # Type-check bound arguments. The primary of a domain action was already
        # checked while resolving its domain, so skip it here.
        for param in action.params:
            if param.name not in bound:
                continue
            if primary_checked and param is action.primary:
                continue
            self.expect(bound[param.name], param.type, scope, f"argument {param.name!r}")

        # Required arguments must be present.
        for param in action.params:
            if param.required and param.name not in bound:
                self.error(f"action {call.name!r} is missing required argument {param.name!r}", call.location)

    # ----- shared checks -----

    def resolve_entity(self, entity: ast.Value, scope: Scope) -> None:
        type_ = self.infer(entity, scope)
        if type_.kind not in ("entity", "unknown"):
            self.error(f"expected an entity, got {_TYPE_NAMES.get(type_.kind, type_.kind)}", entity.location)

    def expect(self, value: ast.Value, kind: str, scope: Scope, what: str) -> None:
        type_ = self.infer(value, scope)
        if type_.kind == "unknown":
            return  # an undeclared alias was already reported; avoid cascading
        if type_.kind != kind:
            self.error(
                f"{what} expects {_TYPE_NAMES.get(kind, kind)}, got {_TYPE_NAMES.get(type_.kind, type_.kind)}",
                value.location,
            )


def analyze(program: ast.Program) -> list[SemanticError]:
    return Analyzer().analyze(program)
