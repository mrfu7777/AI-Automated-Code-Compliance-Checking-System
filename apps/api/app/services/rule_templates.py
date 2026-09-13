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
]
