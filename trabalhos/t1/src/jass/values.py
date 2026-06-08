from __future__ import annotations

import re
from dataclasses import dataclass

_DURATION_RE = re.compile(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$")
_TIME_RE = re.compile(r"@(\d{2}):(\d{2}):(\d{2})$")

@dataclass(frozen=True)
class Duration:
    hours: int = 0
    minutes: int = 0
    seconds: int = 0

    @classmethod
    def parse(cls, text: str) -> "Duration":
        match = _DURATION_RE.fullmatch(text)
        
        if match is None:
            raise ValueError(f"invalid duration: {text!r}")
        
        hours, minutes, seconds = (int(part) if part else 0 for part in match.groups())
        
        return cls(hours, minutes, seconds)

    @property
    def total_seconds(self) -> int:
        return self.hours * 3600 + self.minutes * 60 + self.seconds

    def as_hms(self) -> str:
        total = self.total_seconds
        
        return f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"

    def __str__(self) -> str:
        parts = [f"{v}{u}" for v, u in ((self.hours, "h"), (self.minutes, "m"), (self.seconds, "s")) if v]
        
        return "".join(parts) or "0s"


@dataclass(frozen=True)
class TimeOfDay:
    hour: int
    minute: int
    second: int

    @classmethod
    def parse(cls, text: str) -> "TimeOfDay":
        match = _TIME_RE.fullmatch(text)
        
        if match is None:
            raise ValueError(f"invalid time: {text!r}")
        
        hour, minute, second = (int(part) for part in match.groups())
        
        return cls(hour, minute, second)

    def as_hms(self) -> str:
        return f"{self.hour:02d}:{self.minute:02d}:{self.second:02d}"

    def __str__(self) -> str:
        return f"@{self.as_hms()}"


@dataclass(frozen=True)
class Color:
    red: int
    green: int
    blue: int

    def as_list(self) -> list[int]:
        return [self.red, self.green, self.blue]

    def __str__(self) -> str:
        return f"rgb({self.red}, {self.green}, {self.blue})"


@dataclass(frozen=True)
class EntityRef:
    domain: str
    object_id: str

    @classmethod
    def parse(cls, text: str) -> "EntityRef":
        domain, _, object_id = text.partition(".")
        
        return cls(domain, object_id)

    def __str__(self) -> str:
        return f"{self.domain}.{self.object_id}"
