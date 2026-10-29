"""Dependency-light adapter for the official KOR-Bench release.

The default protocol is the 1,250-question zero-shot core. Pass
include_mixed=True to also load the three standard mixed splits and the
4,000-record Multi-RQ_Hard split.
"""

from __future__ import annotations

import ast
import json
import operator
import re
from functools import lru_cache
from pathlib import Path
from typing import Any


_CATEGORIES = ("operation", "logic", "cipher", "puzzle", "counterfactual")
_MIXED_FILES = ("Multi-Q", "Multi-R", "Multi-RQ", "Multi-RQ_Hard")
_MATH_IDX_RANGES = (
    {18},
    {73, 74, 77},
    {94},
    {115, 116, 117},
    {121, 122, 123, 125},
    {131, 132, 134, 135, 136},
    {141, 143, 149},
    set(range(145, 148)),
    set(range(151, 157)),
    {160, 161, 162},
    {164, 165, 166},
    {170},
    {206, 209},
    set(range(211, 216)),
    {217, 218},
)
_DOUBLE_BRACKET_RE = re.compile(r"\[\[\s*(.*?)\s*\]\]", re.DOTALL)
_BOXED_RE = re.compile(r"\$\\boxed\{(.*?)\}\$", re.DOTALL)
_SINGLE_BRACKET_RE = re.compile(r"\[\s*(.*?)\s*\]", re.DOTALL)


def _source_root() -> Path:
    return Path(__file__).resolve().parents[1] / "sources" / "korbench"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _read_literal_templates(path: Path) -> dict[str, str]:
    """Read the small YAML block-scalar subset used by the official prompts."""
    lines = path.read_text(encoding="utf-8").splitlines()
    templates: dict[str, str] = {}
    active_key: str | None = None
    index = 0
    while index < len(lines):
        line = lines[index]
        key_match = re.fullmatch(r"([A-Za-z0-9_-]+):\s*", line)
        if key_match:
            active_key = key_match.group(1)
            index += 1
            continue
        if active_key is not None and line.strip() == "- |" and line.startswith("  "):
            index += 1
            body: list[str] = []
            while index < len(lines):
                item = lines[index]
                if item and not item.startswith("    "):
                    break
                body.append(item[4:] if item.startswith("    ") else "")
                index += 1
            while body and body[-1] == "":
                body.pop()
            templates[active_key] = "\n".join(body) + "\n"
            continue
        index += 1
    return templates


@lru_cache(maxsize=2)
def _prompts() -> tuple[dict[str, str], str]:
    root = _source_root()
    zero_shot = _read_literal_templates(root / "config" / "prompt" / "zero-shot.yaml")
    mixed = _read_literal_templates(root / "config" / "prompt" / "mixed.yaml")
    core_templates = {
        category: zero_shot[f"{category}_prompt_format"][0]
        if isinstance(zero_shot.get(f"{category}_prompt_format"), list)
        else zero_shot[f"{category}_prompt_format"]
        for category in _CATEGORIES
    }
    mixed_template = mixed.get("prompt_format")
    if isinstance(mixed_template, list):
        mixed_template = mixed_template[0]
    if not mixed_template or len(core_templates) != len(_CATEGORIES):
        raise ValueError("Could not read the official KOR-Bench prompt templates")
    return core_templates, mixed_template


def _index_by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["idx"]): row for row in rows}


def _core_sources() -> tuple[
    dict[str, dict[str, dict[str, Any]]],
    dict[str, dict[str, dict[str, Any]]],
]:
    root = _source_root()
    rules: dict[str, dict[str, dict[str, Any]]] = {}
    samples: dict[str, dict[str, dict[str, Any]]] = {}
    for category in _CATEGORIES:
        rules[category] = _index_by_id(_read_jsonl(root / "data" / category / "rule.jsonl"))
        samples[category] = _index_by_id(_read_jsonl(root / "data" / category / "sample.jsonl"))
    return rules, samples


def _mixed_prompt(
    rule_refs: list[str],
    question_refs: list[str],
    rules: dict[str, dict[str, dict[str, Any]]],
    samples: dict[str, dict[str, dict[str, Any]]],
    template: str,
) -> str:
    rule_texts: list[str] = []
    for ref in rule_refs:
        category, item_id = ref.rsplit("_", 1)
        rule_texts.append(rules[category][item_id]["rule_content"])
    question_texts: list[str] = []
    for ref in question_refs:
        category, item_id = ref.rsplit("_", 1)
        question_texts.append(samples[category][item_id]["question"])
    rules_text = "\n".join(f"{rule}\n" for rule in rule_texts)
    questions_text = "\n".join(
        f"question{position}:\n{question}\n"
        for position, question in enumerate(question_texts, start=1)
    )
    return template.format(rules_text, questions_text)


def load_cases(*, include_mixed: bool = False) -> list[dict[str, Any]]:
    """Load all 1,250 core cases; optionally append all 7,000 mixed cases."""
    root = _source_root()
    if not root.is_dir():
        raise FileNotFoundError(f"Expected the official KOR-Bench checkout at {root}")
    core_templates, mixed_template = _prompts()
    rules, samples = _core_sources()
    cases: list[dict[str, Any]] = []

    for category in _CATEGORIES:
        template = core_templates[category]
        for sample in _read_jsonl(root / "data" / category / "sample.jsonl"):
            rule_id = str(sample["rule_id"])
            rule = rules[category][rule_id]
            metadata: dict[str, Any] = {
                "rule_id": rule_id,
                "source_idx": str(sample["idx"]),
                "source_file": f"data/{category}/sample.jsonl",
                "title": rule.get("title", ""),
                "tag": rule.get("tag", ""),
            }
            if "real_life_answer" in sample:
                metadata["real_life_answer"] = sample["real_life_answer"]
            cases.append({
                "benchmark": "korbench",
                "id": f"{category}_{sample['idx']}",
                "category": category,
                "prompt": template.format(rule["rule_content"], sample["question"]),
                "gold": sample["answer"],
                "metadata": metadata,
            })

    if not include_mixed:
        return cases

    for mode in _MIXED_FILES:
        path = root / "data" / "mixed" / f"{mode}.jsonl"
        for row in _read_jsonl(path):
            question_golds: list[dict[str, Any]] = []
            for ref in row["question_list"]:
                category, sample_id = ref.rsplit("_", 1)
                sample = samples[category][sample_id]
                question_golds.append({
                    "id": ref,
                    "category": category,
                    "answer": sample["answer"],
                    "rule_id": str(sample["rule_id"]),
                    "source_idx": str(sample["idx"]),
                })
            cases.append({
                "benchmark": "korbench",
                "id": f"mixed_{mode}_{row['idx']}",
                "category": "mixed",
                "prompt": _mixed_prompt(
                    row["rule_list"], row["question_list"], rules, samples, mixed_template
                ),
                "gold": question_golds,
                "metadata": {
                    "mixed_mode": mode,
                    "source_idx": str(row["idx"]),
                    "source_file": f"data/mixed/{mode}.jsonl",
                    "rule_list": list(row["rule_list"]),
                    "question_list": list(row["question_list"]),
                },
            })
    return cases


def _bracket_content(text: Any) -> str:
    if not isinstance(text, str):
        return "NULL"
    for pattern in (_DOUBLE_BRACKET_RE, _BOXED_RE, _SINGLE_BRACKET_RE):
        matches = pattern.findall(text)
        if matches:
            return matches[0].strip()
    return "NULL"


def _bracket_text(text: Any, clean_level: str = "basic") -> str:
    content = _bracket_content(text)
    if content == "NULL":
        return "NULL"
    if clean_level == "clean":
        content = content.replace('"', "").replace("\n", "").replace(" ", "")
        content = content.replace("[", "").replace("]", "")
    elif clean_level == "logic":
        content = content.replace('"', "").replace("\n", "").replace(" ", "")
        content = content.replace(".", "")
    elif clean_level == "math":
        content = content.replace('"', "").replace("\n", "")
        content = content.replace("[", "").replace("]", "").replace("$", "")
        return _clean_latex(content)
    return f"[[{content}]]"


def _inner_double_brackets(text: Any) -> str:
    if not isinstance(text, str):
        return "NULL"
    match = re.search(r"\[\[(.*?)\]\]", text, re.DOTALL)
    return match.group(1) if match else "NULL"


def _clean_latex(expression: str) -> str:
    if "=" in expression:
        expression = expression.rsplit("=", 1)[1]
    expression = re.sub(r"\\[()\[\]]", "", expression)
    expression = re.sub(r"\\text\{.*?\}", "", expression)
    expression = re.sub(r"\\(left|right|displaystyle)", "", expression)
    return expression.replace("\\\\", "\\")


def _is_in_math_idx_ranges(index: Any) -> bool:
    try:
        numeric_index = int(index)
    except (TypeError, ValueError):
        return False
    return any(numeric_index in group for group in _MATH_IDX_RANGES)


def _numbers(text: str) -> list[int]:
    return [int(number) for number in re.findall(r"\d+", text)]


def _sorted_inequalities(text: str) -> list[str]:
    values = re.findall(r"(≥|≤)\s*([-]?\d+\.?\d*)", text)
    return sorted("".join(value) for value in values)


def _remove_non_alphanumeric(text: str) -> str:
    return re.sub(r"\W+", "", text)


def _remove_commas_spaces_brackets(text: str) -> str:
    return re.sub(r"[,\s\[\]]+", "", text)


def _safe_arithmetic(expression: str) -> int | float | None:
    """Evaluate the arithmetic-only expressions used by two official puzzle rules."""
    operators: dict[type[ast.operator], Any] = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }

    def visit(node: ast.AST) -> int | float:
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return node.value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = visit(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and type(node.op) in operators:
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 1000:
                raise ValueError("Exponent is outside the safe range")
            return operators[type(node.op)](left, right)
        raise ValueError("Only numeric arithmetic is accepted")

    try:
        tree = ast.parse(expression, mode="eval")
        result = visit(tree)
        return result if isinstance(result, (int, float)) else None
    except (ArithmeticError, SyntaxError, TypeError, ValueError, OverflowError):
        return None


def _compare_math(response: Any, answer: str) -> bool:
    response_text = _bracket_text(response, "math")
    answer_text = _bracket_text(answer, "math")
    if response_text == "NULL":
        return False
    response_parts = response_text.split("or") if "or" in answer_text else [response_text]
    answer_parts = answer_text.split("or") if "or" in answer_text else [answer_text]
    try:
        from sympy import simplify
        from sympy.parsing.latex import parse_latex

        response_expressions = {simplify(parse_latex(part)) for part in response_parts}
        answer_expressions = {simplify(parse_latex(part)) for part in answer_parts}
        return response_expressions == answer_expressions
    except Exception:
        # The reference evaluator falls back to cleaned text when LaTeX parsing fails.
        return response_text == answer_text


def _compare_multi_results(response: Any, answer: str) -> bool:
    response_text = _bracket_text(response, "clean")
    response_text = re.sub(r"\\text\{or\}", "or", response_text)
    if response_text == "NULL":
        return False
    answer_text = _bracket_text(answer, "clean")
    response_parts = sorted(part.strip() for part in response_text.strip("[[]]").split("or"))
    answer_parts = sorted(part.strip() for part in answer_text.strip("[[]]").split("or"))
    return response_parts == answer_parts


def _puzzle_rule_1(response: str, answer: str) -> bool:
    normalize = lambda value: re.sub(r"[^A-Za-z]", "", value).lower()
    return normalize(response) == normalize(answer)


def _puzzle_rule_2(response: str, answer: str) -> bool:
    cleaned = re.sub(r"[^A-Za-z]", "", response).lower()
    return cleaned in answer.split(",")


def _puzzle_rule_3(response: str, answer: str) -> bool:
    response_words = [word for word in re.split(r"\W+", response.lower()) if word]
    return sorted(response_words) == sorted(answer.split(" "))


def _puzzle_rule_4(response: str, answer: str) -> bool:
    cleaned = re.sub(r"[^A-Za-z]", "", response).lower()
    return cleaned in answer


def _puzzle_rule_5(response: str, answer: str) -> bool:
    return sorted(re.sub(r"\s+", "", response).split(",")) == sorted(answer.split(","))


def _puzzle_rule_9(response: str, answer: str) -> bool:
    response = response.replace("×", "*").replace("−", "-")
    answer = answer.replace("×", "*").replace("−", "-")
    response_operators = re.findall(r"[+\-*/]", response.split("=")[0])
    answer_operators = re.findall(r"[+\-*/]", answer.split("=")[0])
    if response_operators != answer_operators:
        return False
    expected = re.search(r"=\s*(-?\d+)", answer)
    if not expected:
        return False
    actual = _safe_arithmetic(response.split("=")[0])
    return actual is not None and actual == int(expected.group(1))


def _puzzle_rule_10(response: str, answer: str) -> bool:
    response = response.replace("×", "*").replace("−", "-").split("=")[0]
    answer = answer.split("\n", 1)[0].split("=")[0]
    if sorted(_remove_non_alphanumeric(response)) != sorted(_remove_non_alphanumeric(answer)):
        return False
    return _safe_arithmetic(response) == 24


def _puzzle_rule_18(response: str, answer: str) -> bool:
    return _remove_commas_spaces_brackets(response) == _remove_commas_spaces_brackets(answer)


def _evaluate_single(
    response: Any,
    answer: str,
    category: str,
    rule_id: str,
    source_index: Any,
) -> bool:
    if category == "logic" and rule_id == "5":
        response_text = _bracket_text(response, "logic")
        if response_text is None:
            return False
        answer_text = _bracket_text(answer, "logic")
        return sorted(response_text.split(";")) == sorted(answer.split(";"))
    if category == "logic":
        return _bracket_text(response, "logic") == _bracket_text(answer, "logic")
    if category == "operation" and str(source_index) in {"178", "179"}:
        return _sorted_inequalities(_bracket_text(response, "clean")) == _sorted_inequalities(answer)
    if category == "operation" and rule_id == "18":
        response_text = _bracket_text(response, "clean")
        answer_text = _inner_double_brackets(answer)
        return "".join(sorted(re.sub(r"\W+", "", response_text))) == "".join(
            sorted(re.sub(r"\W+", "", answer_text))
        )
    if category == "operation" and rule_id in {"23", "24", "25"}:
        return _numbers(_bracket_text(response, "clean")) == _numbers(answer)
    if category == "operation" and _is_in_math_idx_ranges(source_index):
        return _compare_math(response, answer)
    if category == "operation" and "or" in answer:
        return _compare_multi_results(response, answer)
    if category == "puzzle":
        response_text = _inner_double_brackets(response)
        answer_text = _inner_double_brackets(answer)
        methods = {
            "1": _puzzle_rule_1,
            "2": _puzzle_rule_2,
            "3": _puzzle_rule_3,
            "4": _puzzle_rule_4,
            "5": _puzzle_rule_5,
            "9": _puzzle_rule_9,
            "10": _puzzle_rule_10,
            "18": _puzzle_rule_18,
        }
        method = methods.get(rule_id)
        if method:
            return method(response_text, answer_text)
        return _remove_non_alphanumeric(response_text) == _remove_non_alphanumeric(answer_text)
    return _bracket_text(response, "clean") == answer


def _mixed_json(text: Any) -> dict[str, Any] | str:
    if not isinstance(text, str):
        return "NULL"
    matches = re.findall(r"{.*}", text, re.DOTALL)
    if not matches:
        return "NULL"
    raw = re.sub(r"[\x00-\x1f\x7f]", "", matches[-1])
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return "NULL"
    return value if isinstance(value, dict) else "NULL"


def score(case: dict[str, Any], response: str) -> dict[str, Any]:
    """Score a model response with the official category rules and extraction."""
    category = str(case.get("category", ""))
    if category == "mixed":
        parsed = _mixed_json(response)
        if parsed == "NULL":
            return {"correct": False, "extracted": "NULL", "pass_rate": 0.0}
        answers = case.get("gold", [])
        response_values = [str(value) for value in parsed.values()]
        extracted: dict[str, str] = {}
        correct_count = 0
        for position, expected in enumerate(answers):
            if position >= len(response_values):
                break
            answer_text = response_values[position]
            extracted[f"question{position + 1}"] = _bracket_content(answer_text)
            if _evaluate_single(
                answer_text,
                str(expected["answer"]),
                str(expected["category"]),
                str(expected["rule_id"]),
                position,
            ):
                correct_count += 1
        pass_rate = correct_count / len(answers) if answers else 0.0
        return {
            "correct": bool(answers) and correct_count == len(answers),
            "extracted": extracted,
            "pass_rate": pass_rate,
        }

    metadata = case.get("metadata") or {}
    rule_id = str(metadata.get("rule_id", ""))
    answer = str(case.get("gold", ""))
    extracted = _bracket_content(response)
    correct = _evaluate_single(
        response,
        answer,
        category,
        rule_id,
        metadata.get("source_idx"),
    )
    return {"correct": bool(correct), "extracted": extracted}


def validate() -> dict[str, int]:
    """Run lightweight extraction, scoring, and dataset-shape assertions."""
    core = load_cases()
    assert len(core) == 1250, f"Expected 1,250 core cases, got {len(core)}"
    assert all(case["benchmark"] == "korbench" for case in core)
    assert {category: sum(case["category"] == category for case in core) for category in _CATEGORIES} == {
        category: 250 for category in _CATEGORIES
    }
    assert all("###" in case["prompt"] and "Rule:" in case["prompt"] for case in core)
    gold_self_scores = [score(case, case["gold"])["correct"] for case in core]
    assert sum(gold_self_scores) == 1238, (
        "The pinned reference evaluator marks 12 of its own puzzle gold answers incorrect"
    )

    counterfactual = next(case for case in core if case["category"] == "counterfactual")
    gold_value = _bracket_content(counterfactual["gold"])
    assert gold_value != "NULL"
    assert score(counterfactual, counterfactual["gold"]) == {
        "correct": True,
        "extracted": gold_value,
    }
    wrong_value = "B" if gold_value != "B" else "A"
    wrong = score(counterfactual, f"[[{wrong_value}]]")
    assert wrong["correct"] is False and wrong["extracted"] == wrong_value
    assert _bracket_content("Answer: [[ 42 ]]") == "42"
    assert _bracket_content(r"Answer: $\boxed{42}$") == "42"
    assert score(counterfactual, "no bracketed answer") == {
        "correct": False,
        "extracted": "NULL",
    }

    all_cases = load_cases(include_mixed=True)
    assert len(all_cases) == 8250, f"Expected 8,250 core plus mixed cases, got {len(all_cases)}"
    mixed = next(
        case
        for case in all_cases
        if case["category"] == "mixed" and case["metadata"]["mixed_mode"] == "Multi-Q"
    )
    perfect = {
        f"question{position}": item["answer"]
        for position, item in enumerate(mixed["gold"], start=1)
    }
    mixed_result = score(mixed, json.dumps(perfect))
    assert mixed_result["correct"] is True, mixed_result
    assert mixed_result["pass_rate"] == 1.0
    assert mixed_result["extracted"]
    imperfect = dict(perfect)
    imperfect[next(iter(imperfect))] = "[[korbench-validation-wrong]]"
    assert score(mixed, json.dumps(imperfect))["correct"] is False
    for mode in _MIXED_FILES[1:]:
        sample_case = next(
            case
            for case in all_cases
            if case["category"] == "mixed" and case["metadata"]["mixed_mode"] == mode
        )
        answers = {
            f"question{position}": item["answer"]
            for position, item in enumerate(sample_case["gold"], start=1)
        }
        assert score(sample_case, json.dumps(answers))["correct"] is True, mode
    print(
        "korbench validation passed: 1,250 core, 7,000 mixed; "
        "1,238 pinned gold self-scores; correct/wrong/extraction checks passed"
    )
    return {"core_cases": len(core), "mixed_cases": len(all_cases) - len(core)}


if __name__ == "__main__":
    validate()
