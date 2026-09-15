from __future__ import annotations

import json
from typing import Any


def expression_fact_keys(node: Any) -> set[str]:
    """Return every fact key referenced by a rule expression tree."""
    if isinstance(node, dict):
        keys = {str(node["fact"])} if isinstance(node.get("fact"), str) else set()
        for value in node.values():
            keys.update(expression_fact_keys(value))
        return keys
    if isinstance(node, list):
        list_keys: set[str] = set()
        for value in node:
            list_keys.update(expression_fact_keys(value))
        return list_keys
    return set()


def rule_fact_keys(rule: dict[str, Any]) -> set[str]:
    keys = {
        str(item["fact_key"])
        for item in rule.get("inputs", [])
        if isinstance(item, dict) and isinstance(item.get("fact_key"), str)
    }
    keys.update(expression_fact_keys(rule.get("applicability", {})))
    keys.update(expression_fact_keys(rule.get("expression", {})))
    return keys


def changed_fact_keys(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    fact_value = tuple[Any, Any, Any, tuple[str, ...]]

    def values(snapshot: dict[str, Any]) -> dict[tuple[str, str], fact_value]:
        return {
            (
                str(item["key"]),
                json.dumps(item.get("scope_data", {}), sort_keys=True, separators=(",", ":")),
            ): (
                item.get("value"),
                item.get("unit"),
                item.get("id"),
                tuple(sorted(str(value) for value in item.get("evidence_ids", []))),
            )
            for item in snapshot.get("facts", [])
        }

    old, new = values(before), values(after)
    return sorted({key[0] for key in old.keys() | new.keys() if old.get(key) != new.get(key)})


def affected_rule_ids(rule_packs: list[dict[str, Any]], fact_keys: list[str]) -> list[str]:
    changed = set(fact_keys)
    return sorted(
        str(rule["id"])
        for pack in rule_packs
        for rule in pack.get("rules", [])
        if rule_fact_keys(rule) & changed
    )


def dependency_graph(rule_packs: list[dict[str, Any]]) -> dict[str, list[dict[str, str]]]:
    facts = sorted(
        {
            fact_key
            for pack in rule_packs
            for rule in pack.get("rules", [])
            for fact_key in rule_fact_keys(rule)
        }
    )
    rules = [rule for pack in rule_packs for rule in pack.get("rules", [])]
    return {
        "nodes": [
            *[{"id": f"fact:{key}", "kind": "fact", "label": key} for key in facts],
            *[
                {"id": f"rule:{rule['id']}", "kind": "rule", "label": str(rule["code"])}
                for rule in rules
            ],
        ],
        "edges": [
            {"source": f"fact:{key}", "target": f"rule:{rule['id']}"}
            for rule in rules
            for key in sorted(rule_fact_keys(rule))
        ],
    }


def conflict_candidates(rule_packs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Find deterministic conflicts without pretending to interpret legal priority."""
    by_fact: dict[str, list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]]] = {}
    for pack in rule_packs:
        for rule in pack.get("rules", []):
            expression = rule.get("expression", {})
            fact = expression.get("fact") if isinstance(expression, dict) else None
            if isinstance(fact, str) and expression.get("op") in {"eq", "in"}:
                by_fact.setdefault(fact, []).append((pack, rule, expression))
    conflicts = []
    for fact, entries in by_fact.items():
        for index, (left_pack, left_rule, left) in enumerate(entries):
            for right_pack, right_rule, right in entries[index + 1 :]:
                left_values = set(left["value"] if left["op"] == "in" else [left["value"]])
                right_values = set(right["value"] if right["op"] == "in" else [right["value"]])
                if left_values & right_values:
                    continue
                rule_ids = sorted([str(left_rule["id"]), str(right_rule["id"])])
                conflicts.append(
                    {
                        "id": f"{fact}:{':'.join(rule_ids)}",
                        "fact_key": fact,
                        "rule_ids": rule_ids,
                        "rule_codes": [str(left_rule["code"]), str(right_rule["code"])],
                        "authority_levels": [
                            str(left_pack.get("authority_level", "national")),
                            str(right_pack.get("authority_level", "national")),
                        ],
                        "reason": (
                            "The rules require disjoint values; human resolution is required."
                        ),
                    }
                )
    return conflicts
