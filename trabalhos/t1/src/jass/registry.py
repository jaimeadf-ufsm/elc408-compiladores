from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class Param:
    name: str
    type: str
    field: str
    required: bool = False


@dataclass(frozen=True)
class ActionDef:
    name: str
    domain: str | None
    service: str | None
    params: list[Param]
    kind: str = "service"

    @property
    def primary(self) -> Param:
        return self.params[0]

    def param(self, name: str) -> Param | None:
        return next((p for p in self.params if p.name == name), None)


def _entity(name: str = "target", required: bool = True) -> Param:
    return Param(name, "entity", "target", required)


_DOMAIN_ACTIONS: dict[tuple[str, str], ActionDef] = {}

def _register(action: ActionDef) -> None:
    assert action.domain is not None
    _DOMAIN_ACTIONS[(action.name, action.domain)] = action

_register(ActionDef("turn_on", "light", "light.turn_on", [
    _entity(),
    Param("color", "color", "rgb_color"),
    Param("brightness", "number", "brightness"),
    Param("brightness_pct", "number", "brightness_pct"),
    Param("transition", "duration", "transition"),
]))
_register(ActionDef("turn_on", "switch", "switch.turn_on", [_entity()]))
_register(ActionDef("turn_off", "light", "light.turn_off", [_entity()]))
_register(ActionDef("turn_off", "switch", "switch.turn_off", [_entity()]))
_register(ActionDef("turn_off", "media_player", "media_player.turn_off", [_entity()]))
_register(ActionDef("toggle", "light", "light.toggle", [_entity()]))
_register(ActionDef("toggle", "switch", "switch.toggle", [_entity()]))

_register(ActionDef("open", "cover", "cover.open_cover", [_entity()]))
_register(ActionDef("close", "cover", "cover.close_cover", [_entity()]))

_register(ActionDef("volume", "media_player", "media_player.volume_set", [
    _entity(),
    Param("level", "number", "volume_level", required=True),
]))

_register(ActionDef("start", "timer", "timer.start", [_entity()]))

_register(ActionDef("say", "tts", "tts.speak", [
    _entity(),
    Param("player", "entity", "media_player_entity_id"),
    Param("message", "string", "message", required=True),
    Param("language", "string", "language"),
    Param("cache", "bool", "cache"),
]))

_register(ActionDef("run", "automation", "automation.trigger", [
    _entity(),
    Param("skip_condition", "bool", "skip_condition"),
]))


_SPECIAL_ACTIONS: dict[str, ActionDef] = {
    "delay": ActionDef("delay", None, None, [Param("duration", "duration", "", required=True)], kind="delay"),
    "call": ActionDef("call", None, None, [
        Param("service", "string", "", required=True),
        Param("target", "entity", "target"),
        Param("data", "dict", "data"),
    ], kind="call"),
}


def special_action(name: str) -> ActionDef | None:
    return _SPECIAL_ACTIONS.get(name)

def domain_action(name: str, domain: str) -> ActionDef | None:
    return _DOMAIN_ACTIONS.get((name, domain))

def action_domains(name: str) -> list[str]:
    return [domain for (action, domain) in _DOMAIN_ACTIONS if action == name]

def is_known_action(name: str) -> bool:
    return name in _SPECIAL_ACTIONS or bool(action_domains(name))
