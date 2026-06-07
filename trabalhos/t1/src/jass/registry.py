"""The curated action vocabulary.

jass actions are deliberately *not* 1:1 with Home Assistant services. Each action
is defined per target *domain*: the same name on a different kind of device is a
separate capability with its own accepted arguments and its own HA lowering. This
module is the single source of truth for what the language supports; the analyzer
consults it for validation and codegen for lowering.

An action's first parameter (``params[0]``) is its *primary*: for domain actions
that is the target entity whose domain selects the variant. ``delay`` is
domain-agnostic, and ``call`` is the escape hatch — a blind passthrough exempt
from argument validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Value kinds used as parameter types (matched against inferred argument types).
# 'entity' for the primary param additionally permits a list of entities.


@dataclass(frozen=True)
class Param:
    name: str
    type: str
    # HA routing for codegen: "target" → target.entity_id, "" → handled specially
    # (delay/call), anything else → a key under the service's data.
    field: str
    required: bool = False


@dataclass(frozen=True)
class ActionDef:
    name: str
    domain: str | None  # None for domain-agnostic actions (delay)
    service: str | None  # HA service id, or None for specially-lowered actions
    params: list[Param]
    kind: str = "service"  # "service" | "delay" | "call"

    @property
    def primary(self) -> Param:
        return self.params[0]

    def param(self, name: str) -> Param | None:
        return next((p for p in self.params if p.name == name), None)


def _entity(name: str = "target", required: bool = True) -> Param:
    return Param(name, "entity", "target", required)


# Domain-based actions, keyed by (action name, target domain).
_DOMAIN_ACTIONS: dict[tuple[str, str], ActionDef] = {}


def _register(action: ActionDef) -> None:
    _DOMAIN_ACTIONS[(action.name, action.domain)] = action


# turn_on / turn_off / toggle on lights and switches.
_register(ActionDef("turn_on", "light", "light.turn_on", [
    _entity(),
    Param("color", "color", "rgb_color"),
    Param("brightness", "number", "brightness"),
    Param("transition", "duration", "transition"),
]))
_register(ActionDef("turn_on", "switch", "switch.turn_on", [_entity()]))
_register(ActionDef("turn_off", "light", "light.turn_off", [_entity()]))
_register(ActionDef("turn_off", "switch", "switch.turn_off", [_entity()]))
_register(ActionDef("toggle", "light", "light.toggle", [_entity()]))
_register(ActionDef("toggle", "switch", "switch.toggle", [_entity()]))

# Covers.
_register(ActionDef("open", "cover", "cover.open_cover", [_entity()]))
_register(ActionDef("close", "cover", "cover.close_cover", [_entity()]))

# Media players.
_register(ActionDef("volume", "media_player", "media_player.volume_set", [
    _entity(),
    Param("level", "number", "volume_level", required=True),
]))

# Text-to-speech: the primary is the tts engine; an optional media player target
# and the message/language ride in data.
_register(ActionDef("say", "tts", "tts.speak", [
    _entity("engine"),
    Param("target", "entity", "media_player_entity_id"),
    Param("message", "string", "message", required=True),
    Param("language", "string", "language"),
]))

# Trigger another automation.
_register(ActionDef("run", "automation", "automation.trigger", [
    _entity(),
    Param("skip_condition", "bool", "skip_condition"),
]))

# Domain-agnostic / special actions, keyed by name.
_SPECIAL_ACTIONS: dict[str, ActionDef] = {
    "delay": ActionDef("delay", None, None, [Param("duration", "duration", "", required=True)], kind="delay"),
    "call": ActionDef("call", None, None, [
        Param("service", "string", "", required=True),
        Param("target", "entity", "target"),
        Param("data", "dict", "data"),
    ], kind="call"),
}


def special_action(name: str) -> ActionDef | None:
    """Return the definition for a domain-agnostic action (delay/call), if any."""
    return _SPECIAL_ACTIONS.get(name)


def domain_action(name: str, domain: str) -> ActionDef | None:
    """Return the definition for ``name`` on ``domain``, if supported."""
    return _DOMAIN_ACTIONS.get((name, domain))


def action_domains(name: str) -> list[str]:
    """Domains for which a domain-based action ``name`` is defined."""
    return [domain for (action, domain) in _DOMAIN_ACTIONS if action == name]


def is_known_action(name: str) -> bool:
    return name in _SPECIAL_ACTIONS or bool(action_domains(name))
