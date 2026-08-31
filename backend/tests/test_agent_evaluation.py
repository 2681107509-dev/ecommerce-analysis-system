from pathlib import Path

import pytest

from agent_core.evaluation import DEFAULT_DATASET, evaluate_routing, load_cases


def test_default_agent_evaluation_dataset_is_unique_and_balanced():
    cases = load_cases()
    assert len(cases) == 40
    assert len({case.id for case in cases}) == len(cases)
    assert {case.category for case in cases} == {"data", "knowledge", "hybrid", "clarification", "blocked"}


def test_default_agent_routing_accuracy_meets_release_gate():
    report = evaluate_routing(load_cases())
    assert report["accuracy_pct"] >= 90
    assert report["failures"] == []


def test_empty_dataset_is_rejected(tmp_path: Path):
    path = tmp_path / "empty.jsonl"
    path.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="不能为空"):
        load_cases(path)


def test_duplicate_ids_are_rejected(tmp_path: Path):
    path = tmp_path / "duplicate.jsonl"
    row = '{"id":"same","category":"data","query":"销售额多少","expected_intent":"data"}'
    path.write_text(f"{row}\n{row}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="必须唯一"):
        load_cases(path)


def test_default_dataset_location_is_versioned():
    assert DEFAULT_DATASET.exists()
