# Adapted from am-bean/lingOly, licensed CC BY-SA 4.0.
# Changes: benchmark-runner interface and a standard-library exact scorer port.

"""Adapter for the official LingOly benchmark release.

The upstream benchmark ZIP is password-protected to impede scraping. This
adapter reads and decrypts it in memory and never writes the plaintext JSONL.
Questions stay grouped exactly as in the official loader: one case per
question group, with all of that group's subquestion answers scored together.
"""

from __future__ import annotations

import ast
import builtins
import csv
import importlib.util
import json
import re
import unicodedata
import zipfile
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping


BENCHMARK = "lingoly"
DEFAULT_MODEL = "GPT_4o"
_ZIP_PASSWORD = b"lingoly"
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SOURCE_ROOT = _PROJECT_ROOT / "sources" / "lingoly"
_BENCHMARK_ZIP = _SOURCE_ROOT / "testing" / "data" / "benchmark.zip"
_MODEL_LIST = _SOURCE_ROOT / "testing" / "data" / "model_list.json"
_METADATA_CSV = _SOURCE_ROOT / "testing" / "data" / "past-exam-papers.csv"
_OFFICIAL_LOADER_PATH = _SOURCE_ROOT / "testing" / "code" / "load_questions.py"


def _require_source_file(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing official LingOly source file: {path}. Clone "
            "https://github.com/am-bean/lingOly into sources/lingoly."
        )


@lru_cache(maxsize=1)
def _official_loader():
    """Load upstream prompt code while fixing its cwd-relative model-list path."""
    _require_source_file(_OFFICIAL_LOADER_PATH)
    spec = importlib.util.spec_from_file_location(
        "_lingoly_official_load_questions", _OFFICIAL_LOADER_PATH
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot import official LingOly loader: {_OFFICIAL_LOADER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # The upstream function opens ../data/model_list.json relative to the
    # caller's working directory. Redirect only that file; keep its prompt
    # construction and answer formatting untouched and avoid process chdir.
    def source_open(file, *args, **kwargs):
        if Path(file) == Path("../data/model_list.json"):
            file = _MODEL_LIST
        return builtins.open(file, *args, **kwargs)

    module.open = source_open
    return module


def _load_question_sheets() -> list[dict[str, Any]]:
    _require_source_file(_BENCHMARK_ZIP)
    with zipfile.ZipFile(_BENCHMARK_ZIP) as archive:
        names = archive.namelist()
        if "test.jsonl" not in names:
            raise ValueError(
                "The official benchmark ZIP no longer contains testing/data/test.jsonl"
            )
        # Keep the decrypted benchmark in memory. Do not extract test.jsonl.
        raw = archive.read("test.jsonl", pwd=_ZIP_PASSWORD)
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def _literal(value: str) -> Any:
    try:
        return ast.literal_eval(value)
    except (SyntaxError, ValueError):
        return value


def _field_list(value: str) -> list[Any]:
    parsed = _literal(value)
    if parsed is None or parsed == "nan" or parsed == "":
        return []
    return parsed if isinstance(parsed, list) else [parsed]


def _as_int_or_original(value: str) -> int | str | None:
    value = value.strip()
    if not value or value.lower() == "nan":
        return None
    try:
        return int(value)
    except ValueError:
        return value


@lru_cache(maxsize=1)
def _load_sheet_metadata() -> dict[int, dict[str, Any]]:
    _require_source_file(_METADATA_CSV)
    metadata: dict[int, dict[str, Any]] = {}
    with _METADATA_CSV.open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            overall_n = int(row["Overall Question Number"])
            level_and_score = [
                {"level": str(level), "mark_percent": _as_int_or_original(str(score))}
                for level, score in _field_list(row["Level and Score"])
            ]
            metadata[overall_n] = {
                "year": _as_int_or_original(row.get("Year", "")),
                "round": _as_int_or_original(row.get("Round", "")),
                "round_question_number": _as_int_or_original(
                    row.get("Round Question Number", "")
                ),
                "languages": _field_list(row.get("Language", "")),
                "level_and_score": level_and_score,
                "subjects": _field_list(row.get("Subjects", "")),
                "question_format": _field_list(row.get("Question Format", "")),
                "theme": _field_list(row.get("Theme", "")),
                "language_family": _field_list(row.get("Language Family", "")),
                "authors": _field_list(row.get("Author", "")),
                "source_url": row.get("url") or None,
            }
    return metadata


def _cases(no_context: bool, model: str = DEFAULT_MODEL) -> list[dict[str, Any]]:
    loader = _official_loader()
    sheet_metadata = _load_sheet_metadata()
    cases: list[dict[str, Any]] = []

    for sheet in _load_question_sheets():
        overall_n = int(sheet["overall_question_n"])
        source_metadata = sheet_metadata.get(overall_n)
        if source_metadata is None:
            raise ValueError(
                f"No official metadata row for LingOly puzzle sheet {overall_n}"
            )

        question_groups = json.loads(sheet["questions"])
        for question_index, question_group in enumerate(question_groups):
            # Uses the upstream loader's exact prompt construction, including
            # its blank JSON answer template and official model chat wrappers.
            prompt, gold = loader.load_question(
                sheet,
                question_index,
                model=model,
                no_context=no_context,
                cot=False,
            )
            question_n = str(question_group.get("question_n", question_index + 1))
            formats = source_metadata["question_format"]
            category = " / ".join(str(item) for item in formats) or "Unspecified"
            condition = "no_context" if no_context else "full_context"
            case_id = f"{overall_n}:{question_n}:{condition}"
            cases.append(
                {
                    "benchmark": BENCHMARK,
                    "id": case_id,
                    "category": category,
                    "prompt": prompt,
                    "gold": gold,
                    "metadata": {
                        **source_metadata,
                        "overall_question_n": overall_n,
                        "question_n": question_n,
                        "question_index": question_index,
                        "condition": condition,
                        "part_ids": list(gold.keys()),
                    },
                }
            )
    return cases


def load_cases(model: str = DEFAULT_MODEL) -> list[dict[str, Any]]:
    """Load all 204 original question groups with the official full context."""
    return _cases(no_context=False, model=model)


def load_no_context_cases(model: str = DEFAULT_MODEL) -> list[dict[str, Any]]:
    """Load the paired diagnostic with each puzzle context omitted."""
    return _cases(no_context=True, model=model)


def _clean_answer(answer: Any) -> str:
    """Port of official scoring_methods.clean_answer, using only stdlib."""
    clean = str(answer).strip().strip(".")
    clean = re.sub(r"[ ]+", " ", clean)
    clean = clean.lower()
    clean = re.sub(r"\+", "", clean)
    quotes_map = {"‘": "'", "’": "'", "“": '"', "”": '"'}
    for source, replacement in quotes_map.items():
        clean = re.sub(source, replacement, clean)
    return unicodedata.normalize("NFKD", clean)


def _reference_value(value: Any) -> Any:
    # The source JSON normally stores alternatives as arrays. The upstream
    # scorer also accepts a Python-list literal in a string, so retain support.
    if isinstance(value, str):
        parsed = _literal(value)
        if isinstance(parsed, list):
            return parsed
    return value


def _exact_part_score(prediction: Any, reference: Any) -> float:
    reference = _reference_value(reference)
    prediction = "" if prediction is None else str(prediction)

    # Match the upstream scorer's empty-reference convention.
    if isinstance(reference, str) and len(reference) == 0:
        return 1.0
    if isinstance(reference, list) and len(reference) == 0:
        return 1.0
    if len(prediction) == 0:
        return 0.0

    if isinstance(reference, list):
        normalized_prediction = _clean_answer(prediction)
        normalized_options = []
        for option in reference:
            if isinstance(option, list):
                option = ", ".join(str(item) for item in option)
            normalized_options.append(_clean_answer(option))
        # Upstream uses the same exact membership rule for >24 orderings.
        return float(normalized_prediction in normalized_options)
    return float(_clean_answer(reference) == _clean_answer(prediction))


def _parse_response(response: Any, expected_keys: list[str]) -> tuple[dict[str, Any], str | None]:
    if isinstance(response, Mapping):
        if isinstance(response.get("model_answers"), Mapping):
            parsed: Any = response["model_answers"]
        else:
            parsed = response
    elif isinstance(response, str):
        parsed = None
        text = response.strip()
        if text:
            # Accept the official JSON object with surrounding prose or a code
            # fence. Scan object starts without altering answer text.
            for start, char in enumerate(text):
                if char != "{":
                    continue
                try:
                    parsed, _ = json.JSONDecoder().raw_decode(text, start)
                except json.JSONDecodeError:
                    try:
                        candidate = ast.literal_eval(text[start:])
                    except (SyntaxError, ValueError):
                        continue
                    parsed = candidate
                if isinstance(parsed, Mapping):
                    break
                parsed = None
    else:
        parsed = None

    if not isinstance(parsed, Mapping):
        return {key: "" for key in expected_keys}, "No answer object could be extracted"

    extracted: dict[str, Any] = {}
    for key in expected_keys:
        value = parsed.get(key, "")
        if value is None:
            value = ""
        elif isinstance(value, list):
            # Matches the official scorer's listtostr conversion for predictions.
            value = ", ".join(str(item) for item in value)
        elif not isinstance(value, str):
            value = str(value)
        extracted[key] = value
    return extracted, None


def score(case: Mapping[str, Any], response: Any) -> dict[str, Any]:
    """Score one question group with LingOly's normalized exact match."""
    gold = case.get("gold")
    if not isinstance(gold, Mapping) or not gold:
        raise ValueError("LingOly case must have a non-empty gold answer mapping")

    keys = [str(key) for key in gold.keys()]
    normalized_gold = {str(key): value for key, value in gold.items()}
    extracted, parse_error = _parse_response(response, keys)
    part_scores = {
        key: _exact_part_score(extracted.get(key, ""), normalized_gold[key])
        for key in keys
    }
    parts_total = len(part_scores)
    parts_correct = sum(part_scores.values())
    correct = parts_correct == parts_total
    result: dict[str, Any] = {
        "correct": correct,
        "extracted": extracted,
        "score": parts_correct / parts_total,
        "parts_correct": int(parts_correct),
        "parts_total": parts_total,
        "empty_reference_parts": sum(
            _reference_value(value) == "" or _reference_value(value) == []
            for value in normalized_gold.values()
        ),
        "part_scores": part_scores,
    }
    if parse_error:
        result["parse_error"] = parse_error
    return result

