import math
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class Position:
    x: float
    y: float


def _direction(dx: float, dy: float) -> Literal["north", "south", "east", "west"]:
    if abs(dx) >= abs(dy):
        return "east" if dx >= 0 else "west"
    return "south" if dy >= 0 else "north"


_MOVE_DELTAS: dict[str, tuple[float, float]] = {
    "north": (0.0, -1.0),
    "south": (0.0, 1.0),
    "east": (1.0, 0.0),
    "west": (-1.0, 0.0),
}


class VoidEnvironment:
    def __init__(self, width: float = 1000.0, height: float = 1000.0) -> None:
        self.width = width
        self.height = height
        self._positions: dict[str, Position] = {}
        self._message_inbox: dict[str, list[dict]] = {}

    def set_position(self, entity_id: str, pos: Position) -> None:
        self._positions[entity_id] = pos

    def get_position(self, entity_id: str) -> Position | None:
        return self._positions.get(entity_id)

    def remove_entity(self, entity_id: str) -> None:
        self._positions.pop(entity_id, None)
        self._message_inbox.pop(entity_id, None)

    def move(
        self,
        entity_id: str,
        direction: Literal["north", "south", "east", "west"],
        distance: float = 10.0,
    ) -> Position:
        pos = self._positions.get(entity_id, Position(0.0, 0.0))
        dx, dy = _MOVE_DELTAS[direction]
        new_x = max(0.0, min(self.width, pos.x + dx * distance))
        new_y = max(0.0, min(self.height, pos.y + dy * distance))
        new_pos = Position(x=new_x, y=new_y)
        self._positions[entity_id] = new_pos
        return new_pos

    def get_nearby(self, entity_id: str, radius: float = 50.0) -> list[dict]:
        origin = self._positions.get(entity_id)
        if origin is None:
            return []
        result = []
        for other_id, pos in self._positions.items():
            if other_id == entity_id:
                continue
            dist = math.hypot(pos.x - origin.x, pos.y - origin.y)
            if dist <= radius:
                result.append({
                    "id": other_id,
                    "distance": round(dist, 3),
                    "direction": _direction(pos.x - origin.x, pos.y - origin.y),
                })
        return result

    def broadcast(
        self, from_entity: str, message: str, radius: float = 50.0
    ) -> list[str]:
        nearby = self.get_nearby(from_entity, radius)
        reached = []
        for entry in nearby:
            target = entry["id"]
            if target not in self._message_inbox:
                self._message_inbox[target] = []
            self._message_inbox[target].append({
                "from_entity": from_entity,
                "content": message,
                "ticks_ago": 0,
            })
            reached.append(target)
        return reached

    def get_messages(self, entity_id: str) -> list[dict]:
        return self._message_inbox.get(entity_id, [])

    def clear_messages(self) -> None:
        self._message_inbox.clear()

    def age_messages(self) -> None:
        """Increment ticks_ago for all inbox messages. Call once per tick."""
        for msgs in self._message_inbox.values():
            for m in msgs:
                m["ticks_ago"] += 1
