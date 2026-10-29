"""Dependency-light loader and scorer for BIG-Bench Extra Hard (BBEH).

The upstream repository is kept under ``sources/bbeh``. ``load_cases()``
defaults to the published BBEH Mini split; pass ``split="full"`` to load all
full-set examples or ``split="all"`` to load both published files.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any


_ROOT = Path(__file__).resolve().parents[1]
_SOURCE = _ROOT / "sources" / "bbeh"
_MINI_DATA = _SOURCE / "bbeh" / "mini" / "data.json"
_TASKS = _SOURCE / "bbeh" / "benchmark_tasks"
_EVALUATOR = _SOURCE / "bbeh" / "evaluate.py"


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as source_file:
        value = json.load(source_file)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


@lru_cache(maxsize=1)
def _full_rows() -> tuple[tuple[str, int, dict[str, str]], ...]:
    if not _TASKS.is_dir():
        raise FileNotFoundError(f"BBEH source checkout not found: {_SOURCE}")

    rows: list[tuple[str, int, dict[str, str]]] = []
    for path in sorted(_TASKS.glob("*/task.json")):
        task = _read_json(path)
        category = path.parent.name.removeprefix("bbeh_")
        examples = task.get("examples")
        if not isinstance(examples, list):
            raise ValueError(f"Missing examples list in {path}")
        for index, example in enumerate(examples):
            rows.append((category, index, example))
    if not rows:
        raise ValueError(f"No full BBEH examples found under {_TASKS}")
    return tuple(rows)


@lru_cache(maxsize=1)
def _mini_rows() -> tuple[dict[str, str], ...]:
    if not _MINI_DATA.is_file():
        raise FileNotFoundError(f"BBEH Mini data not found: {_MINI_DATA}")
    mini = _read_json(_MINI_DATA).get("examples")
    if not isinstance(mini, list):
        raise ValueError(f"Missing examples list in {_MINI_DATA}")
    return tuple(mini)


@lru_cache(maxsize=1)
def _mini_categories() -> tuple[str, ...]:
    category_by_pair: dict[tuple[str, str], set[str]] = {}
    for category, _, row in _full_rows():
        pair = (row["input"], row["target"])
        category_by_pair.setdefault(pair, set()).add(category)

    categories: list[str] = []
    for index, row in enumerate(_mini_rows()):
        pair = (row["input"], row["target"])
        matches = category_by_pair.get(pair, set())
        if len(matches) != 1:
            raise ValueError(
                "Could not identify one full-set category for BBEH Mini row "
                f"{index}: found {sorted(matches)}"
            )
        categories.append(next(iter(matches)))
    return tuple(categories)


def _case(
    split: str,
    category: str,
    index: int,
    row: dict[str, str],
    source_file: str,
    source_task: str | None = None,
) -> dict[str, Any]:
    if not isinstance(row.get("input"), str) or not isinstance(
        row.get("target"), str
    ):
        raise ValueError(f"Malformed BBEH example in {source_file} at row {index}")

    case: dict[str, Any] = {
        "benchmark": "bbeh",
        "id": f"{split}:{category}:{index:04d}",
        "category": category,
        "prompt": row["input"],
        "gold": row["target"],
        "metadata": {
            "split": split,
            "source_file": source_file,
            "source_index": index,
        },
    }
    if source_task is not None:
        case["metadata"]["source_task"] = source_task
    return case


def load_cases(split: str = "mini") -> list[dict[str, Any]]:
    """Load BBEH Mini, the full set, or both without editing source prompts."""
    if split not in {"mini", "full", "all"}:
        raise ValueError("split must be 'mini', 'full', or 'all'")

    cases: list[dict[str, Any]] = []
    if split in {"mini", "all"}:
        for index, (row, category) in enumerate(zip(_mini_rows(), _mini_categories())):
            source_file = "bbeh/mini/data.json"
            case = _case("mini", category, index, row, source_file)
            case["metadata"]["full_category"] = category
            cases.append(case)

    if split in {"full", "all"}:
        for category, index, row in _full_rows():
            source_task = f"bbeh_{category}"
            cases.append(
                _case(
                    "full",
                    category,
                    index,
                    row,
                    f"bbeh/benchmark_tasks/{source_task}/task.json",
                    source_task,
                )
            )
    return cases


@lru_cache(maxsize=1)
def _official_evaluator() -> ModuleType:
    """Load the upstream scorer, silencing its unguarded demonstration prints."""
    if not _EVALUATOR.is_file():
        raise FileNotFoundError(f"BBEH official evaluator not found: {_EVALUATOR}")
    spec = importlib.util.spec_from_file_location("_bbeh_official_evaluate", _EVALUATOR)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load BBEH evaluator at {_EVALUATOR}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    with contextlib.redirect_stdout(io.StringIO()):
        spec.loader.exec_module(module)
    return module


def score(case: dict[str, Any], response: str) -> dict[str, Any]:
    """Score a response with Google's official evaluator and expose its parse."""
    if not isinstance(response, str):
        raise TypeError("response must be a string")
    gold = case["gold"]
    if not isinstance(gold, str):
        raise TypeError("case['gold'] must be a string")

    evaluator = _official_evaluator()
    return {
        "correct": bool(evaluator.evaluate_correctness(response, gold)),
        "extracted": evaluator.preprocess_sample(response),
    }


def validate() -> None:
    """Run lightweight loader and scorer checks; no model calls are made."""
    mini = load_cases()
    full = load_cases("full")
    both = load_cases("all")
    assert len(mini) == 460, f"Expected 460 Mini rows, got {len(mini)}"
    assert len(full) == 4520, f"Expected 4520 full rows, got {len(full)}"
    assert len(both) == len(mini) + len(full) == 4980
    assert all(case["benchmark"] == "bbeh" for case in mini + full)
    assert len({case["id"] for case in both}) == len(both)

    right = score({"gold": "4"}, "The final answer is: \\boxed{4}.")
    assert right == {"correct": True, "extracted": "4"}, right
    wrong = score({"gold": "4"}, "The final answer is: \\boxed{5}.")
    assert wrong == {"correct": False, "extracted": "5"}, wrong
    extracted = score(
        {"gold": "25.0"}, "Reasoning omitted.\nThe answer is: **25**\nBecause..."
    )
    assert extracted == {"correct": True, "extracted": "25"}, extracted


if __name__ == "__main__":
    validate()
    print("BBEH validation passed: 460 Mini, 4520 full, 4980 selectable rows.")
