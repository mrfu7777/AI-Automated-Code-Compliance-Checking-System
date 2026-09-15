from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RuleTemplate:
    key: str
    title: str
    severity: str
    inputs: list[dict[str, Any]]
    applicability: dict[str, Any]
    expression: dict[str, Any]


def _minimum(key: str, title: str, value: float, unit: str, severity: str = "high") -> RuleTemplate:
    return RuleTemplate(
        key=key,
        title=title,
        severity=severity,
        inputs=[{"fact_key": key, "required": True, "expected_unit": unit}],
        applicability={},
        expression={"op": "gte", "fact": key, "value": value, "unit": unit},
    )


# These are authoring examples, not approved Chinese fire-code interpretations. An architect must
# bind each candidate to a published clause, set its threshold, test it, and review it.
RULE_TEMPLATES = [
    RuleTemplate(
        "building.height_m",
        "Building height scope",
        "high",
        [{"fact_key": "building.height_m", "required": True, "expected_unit": "m"}],
        {},
        {"op": "lte", "fact": "building.height_m", "value": 24, "unit": "m"},
    ),
    RuleTemplate(
        "fire_compartment.area_m2",
        "Fire compartment area limit",
        "critical",
        [{"fact_key": "fire_compartment.area_m2", "required": True, "expected_unit": "m2"}],
        {},
        {"op": "lte", "fact": "fire_compartment.area_m2", "value": 2500, "unit": "m2"},
    ),
    _minimum("exit.count", "Minimum number of safety exits", 2, "count", "critical"),
    _minimum("egress.door_clear_width_m", "Egress door clear width", 0.8, "m"),
    _minimum("egress.corridor_clear_width_m", "Egress corridor clear width", 1.1, "m"),
    _minimum("egress.stair_clear_width_m", "Egress stair clear width", 1.1, "m"),
    RuleTemplate(
        "egress.travel_distance_m",
        "Maximum evacuation travel distance",
        "critical",
        [{"fact_key": "egress.travel_distance_m", "required": True, "expected_unit": "m"}],
        {},
        {"op": "lte", "fact": "egress.travel_distance_m", "value": 40, "unit": "m"},
    ),
    RuleTemplate(
        "fire_elevator.provided",
        "Fire elevator provision",
        "critical",
        [{"fact_key": "fire_elevator.provided", "required": True, "expected_unit": None}],
        {},
        {"op": "eq", "fact": "fire_elevator.provided", "value": True},
    ),
    RuleTemplate(
        "fire_resistance.rating",
        "Required fire resistance rating",
        "critical",
        [{"fact_key": "fire_resistance.rating", "required": True, "expected_unit": None}],
        {},
        {"op": "in", "fact": "fire_resistance.rating", "value": ["I", "II"]},
    ),
    RuleTemplate(
        "sprinkler.provided",
        "Automatic sprinkler provision",
        "critical",
        [{"fact_key": "sprinkler.provided", "required": True, "expected_unit": None}],
        {},
        {"op": "eq", "fact": "sprinkler.provided", "value": True},
    ),
    RuleTemplate(
        "smoke_control.provided",
        "Smoke control provision",
        "critical",
        [{"fact_key": "smoke_control.provided", "required": True, "expected_unit": None}],
        {},
        {"op": "eq", "fact": "smoke_control.provided", "value": True},
    ),
    RuleTemplate(
        "fire_alarm.provided",
        "Automatic fire alarm provision",
        "critical",
        [{"fact_key": "fire_alarm.provided", "required": True, "expected_unit": None}],
        {},
        {"op": "eq", "fact": "fire_alarm.provided", "value": True},
    ),
    RuleTemplate(
        "hydrant.provided",
        "Fire hydrant provision",
        "critical",
        [{"fact_key": "hydrant.provided", "required": True, "expected_unit": None}],
        {},
        {"op": "eq", "fact": "hydrant.provided", "value": True},
    ),
    _minimum("door.count", "Minimum door count", 2, "count"),
    _minimum("stair.count", "Minimum stair count", 2, "count", "critical"),
    _minimum("space.count", "Room inventory present", 1, "count", "medium"),
    _minimum("refuge.area_m2", "Minimum refuge area", 10, "m2", "high"),
    _minimum("fire_lane.width_m", "Fire lane clear width", 4, "m", "critical"),
    _minimum("fire_lane.height_m", "Fire lane clear height", 4, "m", "critical"),
    _minimum("fire_door.clear_width_m", "Fire door clear width", 0.8, "m"),
    _minimum("exit.separation_m", "Safety exit separation", 5, "m", "critical"),
    _minimum("stair.headroom_m", "Stair headroom", 2, "m"),
    RuleTemplate(
        "dead_end.length_m",
        "Maximum dead-end corridor length",
        "high",
        [{"fact_key": "dead_end.length_m", "required": True, "expected_unit": "m"}],
        {},
        {"op": "lte", "fact": "dead_end.length_m", "value": 20, "unit": "m"},
    ),
    RuleTemplate(
        "fire_compartment.count",
        "Fire compartment inventory present",
        "medium",
        [{"fact_key": "fire_compartment.count", "required": True, "expected_unit": "count"}],
        {},
        {"op": "gte", "fact": "fire_compartment.count", "value": 1, "unit": "count"},
    ),
    RuleTemplate(
        "emergency_lighting.provided",
        "Emergency lighting provision",
        "critical",
        [{"fact_key": "emergency_lighting.provided", "required": True, "expected_unit": None}],
        {},
        {"op": "eq", "fact": "emergency_lighting.provided", "value": True},
    ),
]
