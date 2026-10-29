"""PlanBench Blocksworld Hard adapter with a local STRIPS plan evaluator."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


BENCHMARK = "PlanBench Blocksworld Hard - PDDL"
CATEGORY = "PDDL plan generation / exact plan validity"
SOURCE_COMMIT = "1f4d600f4806bedbefebbbe44b168372aaf5060d"
DATA_COMMIT = "1540aef4be296420a6f0dbda1c405181e97ce9a6"
EXPECTED_CASE_COUNT = 110

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SOURCE_ROOT = _REPO_ROOT / "sources" / "planning" / "planbench"
_INSTANCE_ROOT = (
    _SOURCE_ROOT / "llm_planning_analysis" / "instances" / "blocksworld_hard"
)
_DOMAIN_FILE = _INSTANCE_ROOT / "generated_domain.pddl"
_PROBLEM_DIR = _INSTANCE_ROOT / "generated"
_GOLD_FILE = _INSTANCE_ROOT / "info.json"
_TOKEN_RE = re.compile(r";[^\r\n]*|[()]|[^\s()]+")


def _parse_sexpr(text: str) -> list[Any]:
    """Parse the small, comment-free PDDL S-expressions used by this suite."""
    roots: list[Any] = []
    stack: list[list[Any]] = [roots]
    for token in _TOKEN_RE.findall(text):
        if token.startswith(";"):
            continue
        if token == "(":
            node: list[Any] = []
            stack[-1].append(node)
            stack.append(node)
        elif token == ")":
            if len(stack) == 1:
                raise ValueError("Unbalanced closing parenthesis in PDDL")
            stack.pop()
        else:
            stack[-1].append(token.lower())
    if len(stack) != 1 or len(roots) != 1 or not isinstance(roots[0], list):
        raise ValueError("Malformed PDDL S-expression")
    return roots[0]


def _section(expression: list[Any], name: str) -> list[Any]:
    for item in expression[1:]:
        if isinstance(item, list) and item and item[0] == name:
            return item
    raise ValueError(f"Missing PDDL section {name}")


def _literals(expression: Any) -> list[dict[str, Any]]:
    """Flatten positive STRIPS literals and simple negations."""
    if not isinstance(expression, list) or not expression:
        raise ValueError("Expected a PDDL literal expression")
    if expression[0] == "and":
        flattened: list[dict[str, Any]] = []
        for child in expression[1:]:
            flattened.extend(_literals(child))
        return flattened
    if expression[0] == "not":
        if len(expression) != 2 or not isinstance(expression[1], list):
            raise ValueError("Unsupported PDDL negation")
        return [{"atom": list(expression[1]), "positive": False}]
    if not all(isinstance(part, str) for part in expression):
        raise ValueError("Unsupported nested PDDL literal")
    return [{"atom": list(expression), "positive": True}]


def _action_schemas(domain: list[Any]) -> dict[str, dict[str, Any]]:
    schemas: dict[str, dict[str, Any]] = {}
    for form in domain[1:]:
        if not isinstance(form, list) or not form or form[0] != ":action":
            continue
        if len(form) < 4 or (len(form) - 2) % 2:
            raise ValueError("Malformed PDDL action schema")
        attrs = {form[i]: form[i + 1] for i in range(2, len(form), 2)}
        name = form[1]
        parameters = attrs.get(":parameters")
        precondition = attrs.get(":precondition")
        effect = attrs.get(":effect")
        if not isinstance(parameters, list) or precondition is None or effect is None:
            raise ValueError(f"Incomplete PDDL action schema: {name}")
        effects = _literals(effect)
        schemas[name] = {
            "parameters": parameters,
            "preconditions": _literals(precondition),
            "add_effects": [literal["atom"] for literal in effects if literal["positive"]],
            "delete_effects": [literal["atom"] for literal in effects if not literal["positive"]],
        }
    if not schemas:
        raise ValueError("No PDDL action schemas found")
    return schemas


def _problem_facts(problem: list[Any]) -> tuple[list[str], list[list[str]], list[dict[str, Any]]]:
    objects_section = _section(problem, ":objects")
    objects = [part for part in objects_section[1:] if isinstance(part, str)]

    init_section = _section(problem, ":init")
    initial: list[list[str]] = []
    for atom in init_section[1:]:
        if not isinstance(atom, list) or not all(isinstance(part, str) for part in atom):
            raise ValueError("Unsupported initial-state expression")
        initial.append(list(atom))

    goal_section = _section(problem, ":goal")
    goals = _literals(goal_section[1])
    return objects, initial, goals


def _official_prompt(domain_text: str, problem_text: str) -> str:
    """Match PlanBench's task_1_plan_generation_zero_shot_pddl prompt builder."""
    query = (
        "The following is a PDDL specification of a planning problem. The first part, "
        "under the heading [DOMAIN], is the domain file. The second part, under the "
        "heading [QUERY PROBLEM], is the problem file. Using this information, which "
        "is correct, and no further assumptions, find a plan which, when run from the "
        "specified initial state, satisfies the specified goal. Provide your answer as "
        "a sequence of actions in PDDL format. An action ACTION which acts on two "
        "objects OBJ1 and OBJ2 would be written (ACTION OBJ1 OBJ2). Do not provide "
        "anything else in your answer.\n"
    )
    query += "[DOMAIN]\n" + domain_text.strip() + "\n\n"
    if "(define" not in problem_text:
        raise ValueError("Malformed source problem PDDL: missing define")
    # This normalization is part of the upstream prompt generator.
    problem_prompt = "(define" + problem_text.split("(define", 1)[1][:-1].strip() + "\n)"
    query += "[QUERY PROBLEM]\n" + problem_prompt.strip() + "\n\n[PLAN]"
    return query


def load_cases() -> list[dict[str, Any]]:
    """Load all 110 official PDDL prompts, goals, and Fast Downward gold plans."""
    if not (_DOMAIN_FILE.is_file() and _GOLD_FILE.is_file() and _PROBLEM_DIR.is_dir()):
        raise FileNotFoundError(
            "PlanBench source is missing; expected the pinned files under "
            f"{_SOURCE_ROOT}"
        )

    domain_text = _DOMAIN_FILE.read_text(encoding="utf-8")
    domain_expression = _parse_sexpr(domain_text)
    action_schemas = _action_schemas(domain_expression)
    gold_data = json.loads(_GOLD_FILE.read_text(encoding="utf-8"))
    problem_files = sorted(
        _PROBLEM_DIR.glob("instance-*.pddl"),
        key=lambda path: int(path.stem.removeprefix("instance-")),
    )
    if len(problem_files) != EXPECTED_CASE_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_CASE_COUNT} PlanBench problems, found {len(problem_files)}"
        )
    if len(gold_data) != EXPECTED_CASE_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_CASE_COUNT} source gold plans, found {len(gold_data)}"
        )

    cases: list[dict[str, Any]] = []
    for problem_file in problem_files:
        problem_text = problem_file.read_text(encoding="utf-8")
        problem_expression = _parse_sexpr(problem_text)
        objects, initial_state, goal = _problem_facts(problem_expression)
        source_gold = gold_data.get(problem_file.name)
        if not isinstance(source_gold, dict) or not isinstance(source_gold.get("plan"), str):
            raise ValueError(f"Missing source reference plan for {problem_file.name}")

        cases.append(
            {
                "benchmark": BENCHMARK,
                "id": problem_file.stem,
                "category": CATEGORY,
                "prompt": _official_prompt(domain_text, problem_text),
                "gold": {
                    "plan": source_gold["plan"],
                    "length": source_gold.get("length"),
                },
                "metadata": {
                    "source_repository": "https://github.com/harshakokel/PlanBench",
                    "source_commit": SOURCE_COMMIT,
                    "dataset_commit": DATA_COMMIT,
                    "problem_file": problem_file.name,
                    "objects": objects,
                    "initial_state": initial_state,
                    "goal": goal,
                    "action_schemas": action_schemas,
                    "gold_search_stats": source_gold.get("states_info"),
                    "scoring_semantics": (
                        "Any executable plan reaching the positive PDDL goal is correct; "
                        "the source reference plan is not required to match exactly."
                    ),
                },
            }
        )
    return cases


def _extract_plan_lines(response: Any) -> list[str]:
    """Mirror upstream save_gpt3_response line extraction for the PDDL task."""
    if not isinstance(response, str):
        return []
    plan: list[str] = []
    for line in response.split("\n"):
        if not line.startswith("("):
            continue
        if "()" in line or "no actions" in line:
            continue
        plan.append(line.lower().strip())
    return plan


def _parse_action(line: str) -> tuple[str, list[str]] | None:
    if not line.startswith("(") or not line.endswith(")"):
        return None
    parts = line[1:-1].strip().split()
    if not parts:
        return None
    if any("(" in part or ")" in part for part in parts):
        return None
    return parts[0], parts[1:]


def _ground(atom: list[str], bindings: dict[str, str]) -> tuple[str, ...]:
    return tuple(bindings.get(part, part) for part in atom)


def score(case: dict[str, Any], response: Any) -> dict[str, Any]:
    """Execute extracted actions with the source domain's STRIPS semantics."""
    plan_lines = _extract_plan_lines(response)
    metadata = case.get("metadata", {})
    objects = set(metadata.get("objects", []))
    schemas = metadata.get("action_schemas", {})
    state = {tuple(fact) for fact in metadata.get("initial_state", [])}
    valid_actions = 0

    for step_number, line in enumerate(plan_lines, start=1):
        parsed = _parse_action(line)
        if parsed is None:
            return {
                "correct": False,
                "extracted": plan_lines,
                "valid_actions": valid_actions,
                "reason": "malformed_action",
                "failed_step": step_number,
            }
        action_name, arguments = parsed
        schema = schemas.get(action_name)
        if schema is None:
            return {
                "correct": False,
                "extracted": plan_lines,
                "valid_actions": valid_actions,
                "reason": "unknown_action",
                "failed_step": step_number,
                "action": line,
            }
        parameters = schema["parameters"]
        if len(arguments) != len(parameters) or any(arg not in objects for arg in arguments):
            return {
                "correct": False,
                "extracted": plan_lines,
                "valid_actions": valid_actions,
                "reason": "invalid_arguments",
                "failed_step": step_number,
                "action": line,
            }

        bindings = dict(zip(parameters, arguments))
        for literal in schema["preconditions"]:
            fact = _ground(literal["atom"], bindings)
            is_true = fact in state
            if is_true != literal["positive"]:
                return {
                    "correct": False,
                    "extracted": plan_lines,
                    "valid_actions": valid_actions,
                    "reason": "precondition_failed",
                    "failed_step": step_number,
                    "action": line,
                    "precondition": list(fact),
                }

        state.difference_update(_ground(atom, bindings) for atom in schema["delete_effects"])
        state.update(_ground(atom, bindings) for atom in schema["add_effects"])
        valid_actions += 1

    goals = metadata.get("goal", [])
    goal_reached = all(
        (tuple(literal["atom"]) in state) == literal["positive"] for literal in goals
    )
    return {
        "correct": bool(goal_reached),
        "extracted": plan_lines,
        "valid_actions": valid_actions,
        "reason": "goal_reached" if goal_reached else "goal_not_reached",
    }
