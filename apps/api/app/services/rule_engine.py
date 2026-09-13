from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.enums import CheckStatus

ENGINE_VERSION = "m3.engine.v1"
ALLOWED_OPERATORS = {"all", "any", "not", "eq", "ne", "gt", "gte", "lt", "lte", "in"}
UNIT_FACTORS = {
    "mm": ("length", 0.001),
    "cm": ("length", 0.01),
    "m": ("length", 1.0),
    "cm2": ("area", 0.0001),
    "m2": ("area", 1.0),
    "count": ("count", 1.0),
}


class RuleValidationError(ValueError):
    pass


class MissingFactError(ValueError):
    def __init__(self, fact_key: str) -> None:
        super().__init__(f"Required fact is missing: {fact_key}")
        self.fact_key = fact_key


class UnitConversionError(ValueError):
    pass


@dataclass(frozen=True)
class Evaluation:
    status: CheckStatus
    message: str
    fact_keys: list[str]
    operations: list[dict[str, Any]]


def validate_expression(node: dict[str, Any], depth: int = 0) -> None:
    if depth > 10:
        raise RuleValidationError("Expression nesting cannot exceed 10 levels")
    operator = node.get("op")
    if operator not in ALLOWED_OPERATORS:
        raise RuleValidationError(f"Unsupported operator: {operator}")
    if operator in {"all", "any"}:
        children = node.get("conditions")
        if not isinstance(children, list) or not children:
            raise RuleValidationError(f"{operator} requires a non-empty conditions list")
        for child in children:
            if not isinstance(child, dict):
                raise RuleValidationError("Every condition must be an object")
            validate_expression(child, depth + 1)
    elif operator == "not":
        condition = node.get("condition")
        if not isinstance(condition, dict):
            raise RuleValidationError("not requires one condition")
        validate_expression(condition, depth + 1)
    elif not isinstance(node.get("fact"), str) or "value" not in node:
        raise RuleValidationError(f"{operator} requires fact and value")


def _convert(value: Any, source_unit: str | None, target_unit: str | None) -> Any:
    if target_unit is None or source_unit == target_unit:
        return value
    if source_unit is None:
        raise UnitConversionError(f"Expected {target_unit}, but the fact has no unit")
    source = UNIT_FACTORS.get(source_unit)
    target = UNIT_FACTORS.get(target_unit)
    if source is None or target is None or source[0] != target[0]:
        raise UnitConversionError(f"Cannot convert {source_unit} to {target_unit}")
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise UnitConversionError("Only numeric facts can be converted")
    return float(value) * source[1] / target[1]


def _evaluate_node(
    node: dict[str, Any], facts: dict[str, dict[str, Any]], operations: list[dict[str, Any]]
) -> bool:
    operator = str(node["op"])
    if operator in {"all", "any"}:
        values = [_evaluate_node(child, facts, operations) for child in node["conditions"]]
        result = all(values) if operator == "all" else any(values)
        operations.append({"op": operator, "inputs": values, "result": result})
        return result
    if operator == "not":
        value = _evaluate_node(node["condition"], facts, operations)
        result = not value
        operations.append({"op": "not", "input": value, "result": result})
        return result

    fact_key = str(node["fact"])
    fact = facts.get(fact_key)
    if fact is None:
        raise MissingFactError(fact_key)
    left = _convert(fact["value"], fact.get("unit"), node.get("unit"))
    right = node["value"]
    try:
        if operator == "eq":
            result = left == right
        elif operator == "ne":
            result = left != right
        elif operator == "gt":
            result = left > right
        elif operator == "gte":
            result = left >= right
        elif operator == "lt":
            result = left < right
        elif operator == "lte":
            result = left <= right
        else:
            result = left in right
    except TypeError as exception:
        raise RuleValidationError(f"Invalid operands for {operator}") from exception
    operations.append(
        {"op": operator, "fact": fact_key, "actual": left, "expected": right, "result": result}
    )
    return result


def evaluate_rule(
    *,
    title: str,
    applicability: dict[str, Any],
    expression: dict[str, Any],
    inputs: list[dict[str, Any]],
    missing_data_status: str,
    facts: dict[str, dict[str, Any]],
) -> Evaluation:
    validate_expression(expression)
    if applicability:
        validate_expression(applicability)
    required = [str(item["fact_key"]) for item in inputs if item.get("required", True)]
    missing = [key for key in required if key not in facts]
    if missing:
        status = CheckStatus(missing_data_status)
        return Evaluation(status, f"Missing required facts: {', '.join(missing)}", missing, [])
    operations: list[dict[str, Any]] = []
    try:
        if applicability and not _evaluate_node(applicability, facts, operations):
            return Evaluation(
                CheckStatus.NOT_APPLICABLE, f"{title} is not applicable", required, operations
            )
        passed = _evaluate_node(expression, facts, operations)
    except MissingFactError as exception:
        status = CheckStatus(missing_data_status)
        return Evaluation(status, str(exception), [exception.fact_key], operations)
    except UnitConversionError as exception:
        return Evaluation(CheckStatus.MANUAL_REVIEW_REQUIRED, str(exception), required, operations)
    status = CheckStatus.COMPLIANT if passed else CheckStatus.NON_COMPLIANT
    message = f"{title}: {'requirement satisfied' if passed else 'requirement not satisfied'}"
    return Evaluation(status, message, required, operations)
