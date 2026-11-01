"""Offline capture, pooling, reranking, and evaluation for retrieval experiments.

The capture adapter intentionally accepts only the engine response contract used by app.engine:
``{stages: [...], result: {results: [...]}}``. Unknown shapes fail closed so a schema change cannot
silently turn into a benchmark with missing candidates.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

# Sources that put a candidate into the pool before graph expansion. Anything with none of these
# reached the result list only through the citation graph, which is the split the graph arm is about.
HYBRID_SOURCES = frozenset({"bm25", "dense", "hybrid"})

# The engine may key a case by an opaque row id; app/octo_retriever.py swaps in the case name in that
# case so a reader can check it. Mirror that rule, or the pool keys differ from the ones a reviewer sees.
_OPAQUE_ID = re.compile(r"[0-9:._-]+")
# Full commit SHAs, resolved against the Hub on 2026-11-01. A short prefix can go ambiguous, and a
# moving branch would let the model change under a frozen qrels set. Both resolve as historical
# commits; GLiNER2.5-multi-Decide has since moved to e173bca1, deliberately not adopted here.
MODEL_PINS = {
    "decide": ("fastino/GLiNER2.5-Decide", "9d1bfb848cd16d93ee56ccbc59cd92bf0f284d90"),
    "multi-decide": ("fastino/GLiNER2.5-multi-Decide", "9f18c1a7c2d0ba24bd89756bda06af2bf77e2649"),
}


class EvalError(ValueError):
    """An input cannot be evaluated without guessing its meaning."""


def load_json(path: str | Path) -> Any:
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: str | Path, value: Any, *, immutable: bool = False) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    mode = "x" if immutable else "w"
    try:
        with target.open(mode, encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    except FileExistsError as exc:
        raise EvalError(f"{target} already exists; a frozen artifact is never overwritten") from exc


def _percentile(values: list[float], fraction: float) -> float | None:
    """Linear-interpolated percentile; None when there is nothing to summarise."""
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return round(ordered[lower], 3)
    interpolated = ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)
    return round(interpolated, 3)


def normalize_questions(data: Any) -> list[dict[str, str]]:
    """Keep the topic and answerability labels the per-topic and no-answer breakdowns need."""
    questions = data.get("questions") if isinstance(data, dict) else data
    if not isinstance(questions, list) or not questions:
        raise EvalError("question input must be a non-empty list or contain a questions list")
    result = []
    seen = set()
    for row in questions:
        if not isinstance(row, dict):
            raise EvalError("each question must be an object with id and question")
        qid = str(row.get("id") or "").strip()
        question = str(row.get("question") or "").strip()
        split = str(row.get("split") or "development").strip().lower()
        if not qid or not question or split not in {"development", "test"}:
            raise EvalError("each question needs id, question, and development or test split")
        if qid in seen:
            raise EvalError(f"duplicate question id: {qid}")
        seen.add(qid)
        normalized = {"id": qid, "question": question, "split": split}
        for field in ("topic", "group_id", "answerability_expectation"):
            value = str(row.get(field) or "").strip()
            if value:
                normalized[field] = value
        result.append(normalized)
    return result


def validate_dataset(
    data: Any,
    *,
    development: int = 20,
    test: int = 60,
    development_per_topic: int = 5,
    test_per_topic: int = 15,
) -> dict[str, Any]:
    """Check split sizes, per-topic counts, and that no paraphrase group crosses the split.

    A capture is written immutably, so a malformed question set costs a whole run. This runs first.
    """
    questions = normalize_questions(data)
    counts = {"development": 0, "test": 0}
    by_topic: dict[str, dict[str, int]] = {}
    groups: dict[str, set[str]] = {}
    problems: list[str] = []
    for question in questions:
        counts[question["split"]] += 1
        topic = question.get("topic")
        if topic:
            by_topic.setdefault(topic, {"development": 0, "test": 0})[question["split"]] += 1
        else:
            problems.append(f"question {question['id']} has no topic")
        group = question.get("group_id") or question["id"]
        groups.setdefault(group, set()).add(question["split"])
    if counts["development"] != development:
        problems.append(f"expected {development} development questions, found {counts['development']}")
    if counts["test"] != test:
        problems.append(f"expected {test} test questions, found {counts['test']}")
    for topic, topic_counts in sorted(by_topic.items()):
        if topic_counts["development"] != development_per_topic:
            problems.append(f"{topic}: expected {development_per_topic} development questions, found {topic_counts['development']}")
        if topic_counts["test"] != test_per_topic:
            problems.append(f"{topic}: expected {test_per_topic} test questions, found {topic_counts['test']}")
    crossing = sorted(group for group, splits in groups.items() if len(splits) > 1)
    if crossing:
        problems.append(f"paraphrase groups cross the split: {crossing}")
    return {
        "ok": not problems,
        "problems": problems,
        "counts": counts,
        "by_topic": by_topic,
        "question_count": len(questions),
        "dataset_version": data.get("dataset_version") if isinstance(data, dict) else None,
        "review_status": data.get("review_status") if isinstance(data, dict) else None,
    }


def _result_block(response: Any) -> dict[str, Any]:
    if not isinstance(response, dict) or not isinstance(response.get("result"), dict):
        raise EvalError("engine response must contain a result object")
    result = response["result"]
    if not isinstance(result.get("results"), list):
        raise EvalError("supported candidate mapping is result.results; no candidate list was found")
    return result


def _authority_key(case: dict[str, Any], row: dict[str, Any]) -> str:
    """The name the app and a reviewer both use, never an opaque engine row id."""
    case_id = str(case.get("id") or "").strip()
    name = str(case.get("name") or "").strip()
    if name and (not case_id or _OPAQUE_ID.fullmatch(case_id)):
        return name
    if case_id:
        return case_id
    for field in ("work_id", "case_name", "id"):
        value = str(row.get(field) or "").strip()
        if value:
            return value
    return ""


def _provenance(row: dict[str, Any], index: int) -> list[str]:
    """The stages that produced this candidate: `[{"source": "bm25"}, ...]` or bare strings."""
    raw = row.get("provenance")
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise EvalError(f"result.results[{index}].provenance must be a list when present")
    sources = []
    for entry in raw:
        source = entry.get("source") if isinstance(entry, dict) else entry
        if source is None:
            continue
        if not isinstance(source, str):
            raise EvalError(f"result.results[{index}].provenance entries must name a source")
        if source.strip() and source.strip() not in sources:
            sources.append(source.strip())
    return sources


def _graph_stage(response: dict[str, Any]) -> dict[str, Any] | None:
    return next((stage for stage in _stage_rows(response) if (stage.get("stage") or stage.get("name")) == "graph"), None)


def _graph_added_ids(response: dict[str, Any]) -> tuple[set[str], bool]:
    """The documents the graph stage says it added, and whether the stage reported them at all."""
    graph = _graph_stage(response)
    if graph is None or "added" not in graph:
        return set(), False
    added = graph.get("added")
    if not isinstance(added, list):
        raise EvalError("graph stage added must be a list")
    ids = set()
    for row in added:
        if not isinstance(row, dict) or not isinstance(row.get("doc_id"), (str, int)):
            raise EvalError("supported graph addition mapping is graph.added[].doc_id")
        ids.add(str(row["doc_id"]))
    return ids, True


def extract_candidates(query_id: str, response: Any) -> list[dict[str, Any]]:
    """Map engine result rows to one authority candidate each, keeping their raw row."""
    rows = _result_block(response)["results"]
    added_ids, _reported = _graph_added_ids(response)
    candidates = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise EvalError(f"result.results[{index}] must be an object")
        case = row.get("case")
        if case is not None and not isinstance(case, dict):
            raise EvalError(f"result.results[{index}].case must be an object")
        case = case or {}
        key = _authority_key(case, row)
        if not key:
            raise EvalError(f"result.results[{index}] has no supported authority id mapping")
        passages = row.get("passages")
        if passages is not None and not isinstance(passages, list):
            raise EvalError(f"result.results[{index}].passages must be a list")
        first = passages[0] if passages else {}
        if not isinstance(first, dict):
            raise EvalError(f"result.results[{index}].passages[0] must be an object")
        text = first.get("text") or row.get("text")
        if not isinstance(text, str) or not text.strip():
            raise EvalError(f"result.results[{index}] has no passage text")
        score = row.get("score")
        if score is not None and (isinstance(score, bool) or not isinstance(score, (int, float))):
            raise EvalError(f"result.results[{index}].score must be numeric when present")
        provenance = _provenance(row, index)
        candidates.append(
            {
                "query_id": query_id,
                "document_key": key,
                "title": str(case.get("name") or row.get("case_name") or key),
                "text": text.strip(),
                "score": float(score) if score is not None else None,
                "rank": row.get("rank"),
                "provenance": provenance,
                "graph_only": key in added_ids and not (set(provenance) & HYBRID_SOURCES),
                "raw": row,
            }
        )
    return candidates


def _opaque_id(query_id: str, document_key: str) -> str:
    digest = hashlib.sha256(f"{query_id}\0{document_key}".encode("utf-8")).hexdigest()[:20]
    return "d-" + digest


def _stage_rows(response: dict[str, Any]) -> list[dict[str, Any]]:
    stages = response.get("stages")
    if stages is None:
        stages = _result_block(response).get("stages", [])
    if not isinstance(stages, list):
        raise EvalError("engine stages must be a list")
    if any(not isinstance(stage, dict) for stage in stages):
        raise EvalError("each engine stage must be an object")
    return stages


def _completeness(response: dict[str, Any], candidates: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    """Whether this capture can be scored, kept separate from what the graph happened to contribute.

    Three different questions get asked of a capture and conflating them hides the one that matters.
    A pool truncated by `k` is a disclosed limitation. A result list that cannot say which rows came
    only from the graph makes the graph arm unscoreable. A graph addition that never reaches the
    results is neither of those: it is the starvation the experiment is trying to measure, so it is
    counted and reported rather than treated as a defective capture.
    """
    _result_block(response)
    returned = {candidate["document_key"] for candidate in candidates}
    graph_requested = bool(config.get("graph"))
    graph = _graph_stage(response)
    added_ids, reports_additions = _graph_added_ids(response)
    not_returned = sorted(added_ids - returned)

    attributed = [candidate for candidate in candidates if candidate["provenance"]]
    stage_attribution = bool(candidates) and len(attributed) == len(candidates)
    graph_only = [candidate["document_key"] for candidate in candidates if candidate["graph_only"]]

    k = int(config.get("k", 50))
    pools = [int(config.get(name, k)) for name in ("bm25_k", "dense_pool") if config.get(name) is not None]
    truncated = any(pool > k for pool in pools)
    graph_unreported = graph_requested and (graph is None or bool(graph.get("skipped")))
    return {
        "candidate_scope": "returned result.results rows",
        "candidate_pool_complete": stage_attribution and not graph_unreported,
        "pool_truncated_by_k": truncated,
        "stage_attribution_available": stage_attribution,
        "graph_stage_reported": graph is not None,
        "graph_additions_reported": reports_additions,
        "graph_stage_unreported_or_skipped": graph_unreported,
        "graph_added_count": len(added_ids),
        "graph_added_not_returned": not_returned,
        "graph_only_candidates": graph_only,
        "graph_frontier_size": len(graph.get("frontier") or []) if graph else None,
        "graph_edges_scanned": graph.get("edges_scanned") if graph else None,
        "graph_hops": graph.get("hops") if graph else None,
    }


def build_pool(captures: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Build a query-level union, blinded pool, unblinding map, and rank runs."""
    questions: dict[str, dict[str, str]] = {}
    documents: dict[str, dict[str, Any]] = {}
    mappings: dict[str, dict[str, Any]] = {}
    runs = []
    revisions: dict[str, set[str]] = {"corpus_revision": set(), "graph_revision": set()}
    for capture in captures:
        if not isinstance(capture, dict) or not isinstance(capture.get("queries"), list):
            raise EvalError("capture artifact must contain a queries list")
        run_id = str(capture.get("run_id") or "").strip()
        config = capture.get("config")
        if not run_id or not isinstance(config, dict):
            raise EvalError("capture artifact needs run_id and config")
        run = {"run_id": run_id, "config": config, "queries": {}, "capture_complete": True}
        for query in capture["queries"]:
            if not isinstance(query, dict) or not isinstance(query.get("response"), dict):
                raise EvalError("each capture query needs its raw response object")
            qid, question = query.get("id"), query.get("question")
            split = str(query.get("split") or "development")
            if not isinstance(qid, str) or not isinstance(question, str) or split not in {"development", "test"}:
                raise EvalError("capture query needs id, question, and a supported split")
            for field in revisions:
                value = query["response"].get("result", {}).get(field)
                if value:
                    revisions[field].add(str(value))
            metadata = {"id": qid, "question": question, "split": split}
            for field in ("topic", "answerability_expectation"):
                value = str(query.get(field) or "").strip()
                if value:
                    metadata[field] = value
            if qid in questions and questions[qid] != metadata:
                raise EvalError(f"inconsistent question metadata for {qid}")
            questions[qid] = metadata
            candidates = extract_candidates(qid, query["response"])
            quality = _completeness(query["response"], candidates, config)
            query["capture_complete"] = quality["candidate_pool_complete"]
            query["candidate_completeness"] = quality
            run["capture_complete"] = run["capture_complete"] and quality["candidate_pool_complete"]
            entries = []
            for candidate in candidates:
                opaque = _opaque_id(qid, candidate["document_key"])
                if opaque not in documents:
                    documents[opaque] = {"query_id": qid, "opaque_id": opaque, "text": candidate["text"]}
                    mappings[opaque] = {
                        "query_id": qid,
                        "document_key": candidate["document_key"],
                        "title": candidate["title"],
                        "arms": [],
                    }
                elif documents[opaque]["text"] != candidate["text"]:
                    raise EvalError(f"same authority has inconsistent first-passage text: {candidate['document_key']}")
                if run_id not in mappings[opaque]["arms"]:
                    mappings[opaque]["arms"].append(run_id)
                entries.append(
                    {
                        "doc_id": opaque,
                        "score": candidate["score"],
                        "rank": candidate["rank"],
                        "provenance": candidate["provenance"],
                        "graph_only": candidate["graph_only"],
                        "raw": candidate["raw"],
                    }
                )
            run["queries"].setdefault(qid, [])
            if run["queries"][qid]:
                raise EvalError(f"capture {run_id} has duplicate query id {qid}")
            run["queries"][qid] = entries
        runs.append(run)
    for field, values in revisions.items():
        if len(values) > 1:
            raise EvalError(
                f"captures span more than one {field} ({', '.join(sorted(values))}); the corpus changed between arms, so re-capture both on one snapshot"
            )
    pool = {
        "format": "retrieval-eval-pool-v1",
        "questions": list(questions.values()),
        "documents": list(documents.values()),
        "blinded": True,
        "id_method": "sha256(query_id + NUL + authority_id), truncated to 80 bits",
        "corpus_revision": next(iter(revisions["corpus_revision"]), None),
        "graph_revision": next(iter(revisions["graph_revision"]), None),
    }
    return pool, mappings, runs


def _judgment_map(qrels: Any) -> dict[str, dict[str, int]]:
    if not isinstance(qrels, dict) or not isinstance(qrels.get("judgments"), list):
        raise EvalError("qrels must contain judgments with query_id, opaque_id, and grade")
    result: dict[str, dict[str, int]] = {}
    for row in qrels["judgments"]:
        if not isinstance(row, dict):
            raise EvalError("each judgment must be an object")
        qid, docid, grade = row.get("query_id"), row.get("opaque_id"), row.get("grade")
        if not isinstance(qid, str) or not isinstance(docid, str) or isinstance(grade, bool) or grade not in (0, 1, 2):
            raise EvalError("judgments require string ids and an integer grade of 0, 1, or 2")
        if docid in result.setdefault(qid, {}):
            raise EvalError(f"duplicate judgment for {qid}/{docid}")
        result[qid][docid] = grade
    return result


def _metrics(ranked: list[dict[str, Any]], grades: dict[str, int]) -> dict[str, float]:
    docs = [row["doc_id"] for row in ranked]
    rel = [grades[docid] for docid in docs]
    dcg = sum((2**grade - 1) / math.log2(rank + 1) for rank, grade in enumerate(rel[:10], start=1))
    ideal = sorted(grades.values(), reverse=True)[:10]
    idcg = sum((2**grade - 1) / math.log2(rank + 1) for rank, grade in enumerate(ideal, start=1))
    known_relevant = sum(grade > 0 for grade in grades.values())
    return {
        "ndcg@10": dcg / idcg if idcg else 0.0,
        "precision@3": sum(grade > 0 for grade in rel[:3]) / 3,
        "precision@10": sum(grade > 0 for grade in rel[:10]) / 10,
        "known_relevant_recall@10": sum(grade > 0 for grade in rel[:10]) / known_relevant if known_relevant else 0.0,
    }


def _graph_contribution(ranked: list[dict[str, Any]], grades: dict[str, int]) -> dict[str, int]:
    """What the graph arm added that hybrid alone would not have surfaced, and where it landed.

    A candidate counts as graph-only from its own `provenance`, so this is read per arm rather than
    per pool. Only queries with complete judgments are reported, because an ungraded candidate has
    no known contribution.
    """
    graph_only = [row for row in ranked if row.get("graph_only")]
    relevant = [row for row in graph_only if grades.get(row["doc_id"], 0) > 0]
    return {
        "graph_only_candidates": len(graph_only),
        "graph_only_relevant": len(relevant),
        "graph_only_relevant_in_top3": sum(1 for row in ranked[:3] if row.get("graph_only") and grades.get(row["doc_id"], 0) > 0),
        "graph_only_relevant_in_top10": sum(1 for row in ranked[:10] if row.get("graph_only") and grades.get(row["doc_id"], 0) > 0),
    }


def score_run(run: dict[str, Any], pool: dict[str, Any], qrels: Any, *, split: str | None = None) -> dict[str, Any]:
    judgments = _judgment_map(qrels)
    questions = {row["id"]: row for row in pool.get("questions", [])}
    pool_docs: dict[str, set[str]] = {}
    for row in pool.get("documents", []):
        pool_docs.setdefault(row["query_id"], set()).add(row["opaque_id"])
    output = {}
    for qid, question in questions.items():
        if split and question["split"] != split:
            continue
        expected = pool_docs.get(qid, set())
        grades = judgments.get(qid, {})
        coverage = len(expected & grades.keys()) / len(expected) if expected else 0.0
        ranked = run.get("queries", {}).get(qid, [])
        unknown_run_ids = {row.get("doc_id") for row in ranked} - expected
        if unknown_run_ids:
            raise EvalError(f"run {run.get('run_id')} has ids outside the pool for {qid}")
        missing = sorted(expected - grades.keys())
        if missing:
            metrics = None
            reason = "all pooled candidates need explicit 0/1/2 judgments before metrics are reported"
        else:
            metrics = _metrics(ranked, grades)
            reason = None
        output[qid] = {
            "split": question["split"],
            "label_coverage": coverage,
            "judged_candidates": len(expected) - len(missing),
            "pooled_candidates": len(expected),
            "metrics": metrics,
            "graph_contribution": _graph_contribution(ranked, grades) if metrics is not None else None,
            "withheld_reason": reason,
        }
    available = [row["metrics"] for row in output.values() if row["metrics"] is not None]
    names = ("ndcg@10", "precision@3", "precision@10", "known_relevant_recall@10")
    averages = {name: sum(row[name] for row in available) / len(available) for name in names} if available else None
    contributions = [row["graph_contribution"] for row in output.values() if row["graph_contribution"] is not None]
    totals = {name: sum(row[name] for row in contributions) for name in contributions[0]} if contributions else None
    return {
        "run_id": run.get("run_id"),
        "split": split or "all",
        "label_coverage_rule": "queries score only when every pooled candidate has a 0/1/2 judgment",
        "known_relevant_recall_rule": "denominator is all grade-1 or grade-2 candidates in the fully judged pool",
        "scored_query_count": len(available),
        "query_count": len(output),
        "macro_metrics": averages,
        "graph_contribution_totals": totals,
        "breakdowns": _breakdowns(output, questions),
        "queries": output,
    }


def _breakdowns(output: dict[str, dict[str, Any]], questions: dict[str, dict[str, str]]) -> dict[str, dict[str, Any]]:
    """Per-topic and per-answerability averages, kept apart so neither hides the other.

    A no-answer or underspecified question is not scored as a retrieval win just because something was
    returned, so those groups are reported on their own rather than folded into the overall average.
    """
    names = ("ndcg@10", "precision@3", "precision@10", "known_relevant_recall@10")
    grouped: dict[str, dict[str, list[dict[str, float]]]] = {}
    for qid, row in output.items():
        if row["metrics"] is None:
            continue
        question = questions.get(qid, {})
        for field in ("topic", "answerability_expectation"):
            label = question.get(field)
            if label:
                grouped.setdefault(field, {}).setdefault(label, []).append(row["metrics"])
    return {
        field: {
            label: {
                "scored_query_count": len(rows),
                "macro_metrics": {name: sum(row[name] for row in rows) / len(rows) for name in names},
            }
            for label, rows in sorted(labels.items())
        }
        for field, labels in grouped.items()
    }


def compare_runs(
    run_a: dict[str, Any],
    run_b: dict[str, Any],
    pool: dict[str, Any],
    qrels: Any,
    *,
    split: str | None = None,
    resamples: int = 2000,
    seed: int = 0,
    confidence: float = 0.95,
) -> dict[str, Any]:
    """Paired bootstrap interval for each metric difference between two runs.

    Only queries fully judged under the same pool are paired, so the two arms are compared on the same
    questions rather than on two different subsets. A metric whose interval covers zero does not
    separate the arms, and with a small held-out set that is the expected outcome.
    """
    if resamples < 1:
        raise EvalError("resamples must be at least 1")
    if not 0.0 < confidence < 1.0:
        raise EvalError("confidence must be between 0 and 1")
    scored_a = score_run(run_a, pool, qrels, split=split)
    scored_b = score_run(run_b, pool, qrels, split=split)
    paired = sorted(
        qid for qid, row in scored_a["queries"].items() if row["metrics"] is not None and scored_b["queries"].get(qid, {}).get("metrics") is not None
    )
    names = ("ndcg@10", "precision@3", "precision@10", "known_relevant_recall@10")
    differences = {name: [scored_a["queries"][qid]["metrics"][name] - scored_b["queries"][qid]["metrics"][name] for qid in paired] for name in names}
    rng = random.Random(seed)
    tail = (1.0 - confidence) / 2.0
    metrics: dict[str, Any] = {}
    for name, values in differences.items():
        observed = sum(values) / len(values) if values else None
        interval = [None, None]
        if values:
            means = []
            for _ in range(resamples):
                sample = [values[rng.randrange(len(values))] for _ in range(len(values))]
                means.append(sum(sample) / len(sample))
            means.sort()
            interval = [_percentile(means, tail), _percentile(means, 1.0 - tail)]
        separates = interval[0] is not None and (interval[0] > 0 or interval[1] < 0)
        metrics[name] = {
            "observed_difference": observed,
            "ci_low": interval[0],
            "ci_high": interval[1],
            "separates_arms": separates,
        }
    separates_any = any(row["separates_arms"] for row in metrics.values())
    return {
        "run_a": run_a.get("run_id"),
        "run_b": run_b.get("run_id"),
        "direction": "a positive difference means run_a scored higher",
        "split": split or "all",
        "paired_query_count": len(paired),
        "resamples": resamples,
        "seed": seed,
        "confidence": confidence,
        "interval_method": "paired bootstrap over queries, resampled with replacement",
        "metrics": metrics,
        "separates_arms": separates_any,
        "inconclusive": not separates_any,
        "note": (
            "No metric interval excludes zero, so the data cannot separate the arms."
            if not separates_any
            else "At least one metric interval excludes zero; read the paired query count before claiming a win."
        ),
    }


REVIEW_COLUMNS = (
    "query_id",
    "question",
    "document_id",
    "passage",
    "grade",
    "authority_current",
    "reviewer",
    "notes",
)


def review_sheet(pool: dict[str, Any], *, seed: int = 0, max_chars: int | None = 1200) -> list[dict[str, str]]:
    """A blinded sheet: no system name, no rank, and passages shuffled per query.

    Grade stays empty so a reviewer supplies it; nothing here carries a model's opinion.
    """
    questions = {row["id"]: row for row in pool.get("questions", [])}
    by_query: dict[str, list[dict[str, Any]]] = {}
    for document in pool.get("documents", []):
        by_query.setdefault(document["query_id"], []).append(document)
    rows = []
    for qid in sorted(by_query):
        documents = list(by_query[qid])
        random.Random(f"{seed}:{qid}").shuffle(documents)
        for document in documents:
            text = str(document.get("text") or "")
            if max_chars is not None and len(text) > max_chars:
                text = text[:max_chars]
            rows.append(
                {
                    "query_id": qid,
                    "question": str(questions.get(qid, {}).get("question") or ""),
                    "document_id": document["opaque_id"],
                    "passage": text,
                    "grade": "",
                    "authority_current": "",
                    "reviewer": "",
                    "notes": "",
                }
            )
    return rows


def write_review_sheet(path: str | Path, rows: list[dict[str, str]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def qrels_from_review(
    path: str | Path,
    pool: dict[str, Any],
    *,
    qrels_version: str,
    require_complete: bool = True,
) -> dict[str, Any]:
    """Turn a reviewed sheet into qrels, refusing anything the metrics could not honestly use."""
    if not str(qrels_version).strip():
        raise EvalError("qrels need a version so a comparison can name the labels it used")
    pooled = {(row["query_id"], row["opaque_id"]) for row in pool.get("documents", [])}
    with Path(path).open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise EvalError("the review sheet has no header row")
        missing = [column for column in ("query_id", "document_id", "grade") if column not in reader.fieldnames]
        if missing:
            raise EvalError(f"the review sheet is missing columns: {missing}")
        judgments: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        ungraded: list[str] = []
        reviewers: set[str] = set()
        for line, row in enumerate(reader, start=2):
            qid = str(row.get("query_id") or "").strip()
            docid = str(row.get("document_id") or "").strip()
            raw_grade = str(row.get("grade") or "").strip()
            if not qid or not docid:
                raise EvalError(f"review sheet line {line} has no query or document id")
            if (qid, docid) in seen:
                raise EvalError(f"duplicate judgment for {qid}/{docid}")
            seen.add((qid, docid))
            if (qid, docid) not in pooled:
                raise EvalError(f"judgment for {qid}/{docid} is not in the blinded pool")
            reviewer = str(row.get("reviewer") or "").strip()
            if reviewer:
                reviewers.add(reviewer)
            if not raw_grade:
                ungraded.append(f"{qid}/{docid}")
                continue
            if raw_grade not in {"0", "1", "2"}:
                raise EvalError(f"grade for {qid}/{docid} must be 0, 1, or 2, found {raw_grade!r}")
            judgment = {"query_id": qid, "opaque_id": docid, "grade": int(raw_grade)}
            authority = str(row.get("authority_current") or "").strip()
            if authority:
                judgment["authority_current"] = authority
            if reviewer:
                judgment["reviewer"] = reviewer
            notes = str(row.get("notes") or "").strip()
            if notes:
                judgment["notes"] = notes
            judgments.append(judgment)
    unjudged = sorted(pooled - seen)
    if require_complete and (ungraded or unjudged):
        detail = ungraded[:5] + unjudged[:5]
        raise EvalError(f"{len(ungraded) + len(unjudged)} pooled candidates have no grade, e.g. {detail}")
    return {
        "qrels_version": str(qrels_version).strip(),
        "source": str(path),
        "reviewers": sorted(reviewers),
        "judged_candidates": len(judgments),
        "pooled_candidates": len(pooled),
        "label_coverage": len(judgments) / len(pooled) if pooled else 0.0,
        "judgments": judgments,
    }


def assert_selection_split(split: str) -> None:
    if split != "development":
        raise EvalError("configuration selection is allowed on the development split only")


def rank_fusion(runs: list[dict[str, Any]], *, constant: int = 60) -> dict[str, Any]:
    """Fuse captured rankings with reciprocal rank fusion."""
    if len(runs) < 2 or constant < 0:
        raise EvalError("rank fusion needs at least two runs and a non-negative constant")
    fused: dict[str, list[dict[str, Any]]] = {}
    qids = set().union(*(run.get("queries", {}).keys() for run in runs))
    for qid in qids:
        scores: dict[str, float] = {}
        for run in runs:
            seen = set()
            for rank, row in enumerate(run.get("queries", {}).get(qid, []), start=1):
                docid = row.get("doc_id")
                if docid not in seen:
                    scores[docid] = scores.get(docid, 0.0) + 1.0 / (constant + rank)
                    seen.add(docid)
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        fused[qid] = [{"doc_id": docid, "score": score, "rank": rank} for rank, (docid, score) in enumerate(ranked, 1)]
    return {
        "run_id": "rrf-" + "+".join(str(run.get("run_id")) for run in runs),
        "queries": fused,
        "fusion": {"method": "reciprocal_rank_fusion", "constant": constant},
    }


def _confidence(result: Any) -> float:
    """Map one GLiNER classification to a relevance score in [0, 1].

    An unlabelled passage is a real outcome, not a schema error: the model returns no label when
    nothing clears the threshold, and a reranker has to score that passage low rather than abort the
    run. A label without a confidence is a genuine shape change, so it still fails closed.
    """
    if not isinstance(result, dict):
        raise EvalError("GLiNER output must be a result object")
    row = result.get("relevance")
    if row is None or row == {} or row == [] or row == "":
        return 0.0
    if not isinstance(row, dict):
        raise EvalError("GLiNER relevance must return a label with a confidence")
    if row.get("label") not in {"yes", "no"} or not isinstance(row.get("confidence"), (int, float)):
        raise EvalError("GLiNER relevance must return yes/no label and numeric confidence")
    return float(row["confidence"]) if row["label"] == "yes" else 1.0 - float(row["confidence"])


def _http_scorer(endpoint: str, key: str):
    """Call the documented GLiNER2 contract directly, for a host that serves the model elsewhere.

    The SDK would do this too, but importing `gliner2` pulls torch even for a client call, and the
    machine doing the reranking here is not the one running the model.
    """
    url = endpoint.rstrip("/") + "/gliner-2"

    def score(prompt: str) -> dict[str, Any]:
        payload = {
            "task": "classify_text",
            "text": prompt,
            "schema": {"categories": ["yes", "no"]},
            "threshold": 0.0,
            "include_confidence": True,
            "include_spans": False,
            "format_results": True,
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"X-API-Key": key, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                body = json.loads(response.read() or b"{}")
        except urllib.error.HTTPError as error:
            raise EvalError(f"GLiNER2 endpoint answered {error.code} at {url}") from error
        except Exception as error:
            raise EvalError(f"GLiNER2 endpoint unreachable at {url}: {type(error).__name__}") from error
        if not isinstance(body, dict):
            raise EvalError("GLiNER2 endpoint did not answer a JSON object")
        return {"relevance": body.get("classification", body)}

    return score


def _gliner_client(*, model_key: str, endpoint: str | None, api_key: str | None):
    """Build a scorer plus the record of what actually scored, for local or served inference.

    A served endpoint takes the model from the server, not from the request: the API payload carries
    no model or revision. So a run against an endpoint must record that the pin was not enforced
    instead of claiming the pinned weights were used.
    """
    if endpoint:
        key = api_key or os.environ.get("FASTINO_API_KEY") or os.environ.get("GLINER2_API_KEY")
        if not key:
            raise EvalError("set FASTINO_API_KEY or GLINER2_API_KEY for the GLiNER2 endpoint")
        sdk_class = None
        try:
            from gliner2 import GLiNER2API as sdk_class
        except ImportError:
            sdk_class = None
        if sdk_class is None:
            score, used = _http_scorer(endpoint, key), "http"
        else:
            sdk = sdk_class(api_key=key, api_base_url=endpoint)

            def score(prompt: str) -> dict[str, Any]:
                return sdk.classify_text(
                    prompt,
                    {"relevance": ["yes", "no"]},
                    threshold=0.0,
                    format_results=True,
                    include_confidence=True,
                )

            used = "sdk"
        return score, {
            "mode": "remote",
            "endpoint": endpoint,
            "client": used,
            "model": None,
            "revision": None,
            "model_pin_enforced": False,
            "note": "the endpoint chooses the model; the local pin cannot be verified over the API",
        }

    if model_key not in MODEL_PINS:
        raise EvalError(f"unknown model key: {model_key}")
    try:
        from gliner2 import AutoExtractor
    except ImportError as exc:
        raise EvalError(
            f"local GLiNER2 is unavailable ({exc.name or exc}); it needs torch installed. Serve the model elsewhere and pass --endpoint, or install torch here"
        ) from exc
    model_id, revision = MODEL_PINS[model_key]
    extractor = AutoExtractor.from_pretrained(model_id, revision=revision)

    def score(prompt: str) -> dict[str, Any]:
        # threshold=0.0 keeps the label for a weak passage: this is a ranking signal, so a score of
        # 0.51 must outrank 0.50 rather than both collapsing to "nothing above the threshold".
        return extractor.classify_text(
            prompt,
            {"relevance": ["yes", "no"]},
            threshold=0.0,
            format_results=True,
            include_confidence=True,
        )

    return score, {"mode": "local", "model": model_id, "revision": revision, "model_pin_enforced": True}


def gliner_rerank(
    pool: dict[str, Any],
    *,
    model_key: str = "decide",
    split: str = "development",
    endpoint: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Score pooled passages; confidence is a ranking signal, not a calibrated probability."""
    scorer, provenance = _gliner_client(model_key=model_key, endpoint=endpoint, api_key=api_key)
    questions = {row["id"]: row for row in pool["questions"] if row["split"] == split}
    ranked: dict[str, list[dict[str, Any]]] = {qid: [] for qid in questions}
    for document in pool["documents"]:
        qid = document["query_id"]
        if qid not in questions:
            continue
        prompt = f"Question: {questions[qid]['question']}\n\nPassage:\n{document['text']}"
        ranked[qid].append({"doc_id": document["opaque_id"], "score": _confidence(scorer(prompt))})
    for rows in ranked.values():
        rows.sort(key=lambda row: (-row["score"], row["doc_id"]))
        for index, row in enumerate(rows, start=1):
            row["rank"] = index
    return {
        "run_id": f"gliner-{provenance['mode']}-{model_key}",
        **provenance,
        "score_meaning": "ranking signal from GLiNER confidence; not a calibrated probability",
        "split": split,
        "queries": ranked,
    }


def capture(
    questions_path: str,
    output_path: str,
    *,
    graph: bool,
    k: int = 50,
    rerank: bool = False,
    rerank_k: int = 30,
) -> None:
    if k < 1 or k > 50:
        raise EvalError("the supported engine k limit is 50")
    if rerank_k < 1 or rerank_k > 100:
        raise EvalError("the supported engine rerank_k limit is 100")
    sys.path.insert(0, str(ROOT))
    from app import engine

    questions = normalize_questions(load_json(questions_path))
    config = {
        "k": k,
        "bm25_k": 100,
        "dense": True,
        "dense_pool": 100,
        "graph": graph,
        "graph_seed_docs": 10,
        "rerank": rerank,
        "rerank_k": rerank_k,
        "jev": False,
    }
    queries = []
    for question in questions:
        started = time.perf_counter()
        try:
            response = engine.retrieve(question["question"], **config)
            _result_block(response)
            _stage_rows(response)
            candidates = extract_candidates(question["id"], response)
            quality = _completeness(response, candidates, config)
            record = {
                **question,
                "response": response,
                "capture_complete": quality["candidate_pool_complete"],
                "candidate_completeness": quality,
                "engine_elapsed_ms": response["result"].get("elapsed_ms"),
            }
        except Exception as exc:
            # Engine errors contain a safe reason; never include request headers or environment values.
            reason = getattr(exc, "reason", None) or str(exc)
            record = {**question, "error": f"{type(exc).__name__}: {str(reason)[:300]}"}
        record["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 3)
        queries.append(record)

    warm = [query["elapsed_ms"] for query in queries[1:] if "error" not in query]
    revisions: dict[str, set[str]] = {"corpus_revision": set(), "graph_revision": set()}
    for record in queries:
        result = (record.get("response") or {}).get("result") or {}
        for field in revisions:
            if result.get(field):
                revisions[field].add(str(result[field]))
    artifact = {
        "format": "retrieval-eval-capture-v1",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "run_id": (f"graph-{int(graph)}-rerank-{int(rerank)}-rk{rerank_k}-k{k}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}"),
        "config": config,
        "corpus_revisions": sorted(revisions["corpus_revision"]),
        "graph_revisions": sorted(revisions["graph_revision"]),
        "timing": {
            "cold_start_ms": queries[0]["elapsed_ms"] if queries else None,
            "warm_p50_ms": _percentile(warm, 0.5),
            "warm_p95_ms": _percentile(warm, 0.95),
            "warm_query_count": len(warm),
            "clock": "client wall time around one engine call, model load included in the first call",
        },
        "queries": queries,
    }
    write_json(output_path, artifact, immutable=True)


def _cmd_questions(args: argparse.Namespace) -> None:
    report = validate_dataset(load_json(args.questions))
    if args.output:
        write_json(args.output, report)
    if not report["ok"]:
        raise EvalError("question set does not match the declared splits: " + "; ".join(report["problems"]))


def _cmd_pool(args: argparse.Namespace) -> None:
    captures = [load_json(path) for path in args.captures]
    pool, mapping, runs = build_pool(captures)
    write_json(args.pool, pool)
    write_json(args.mapping, mapping)
    write_json(args.runs, runs)


def _cmd_score(args: argparse.Namespace) -> None:
    runs = _load_runs([args.run])
    if args.run_id:
        runs = [run for run in runs if str(run.get("run_id")) == args.run_id]
        if not runs:
            raise EvalError(f"{args.run} holds no run with id {args.run_id}")
    if len(runs) != 1:
        raise EvalError(f"score reads one arm at a time; {args.run} holds {len(runs)} runs, so pass --run-id or use compare")
    if args.for_selection:
        assert_selection_split(args.split)
    write_json(args.output, score_run(runs[0], load_json(args.pool), load_json(args.qrels), split=args.split))


def _cmd_gliner(args: argparse.Namespace) -> None:
    endpoint = None if args.local else (args.endpoint or os.environ.get("GLINER2_API_BASE_URL"))
    write_json(
        args.output,
        gliner_rerank(load_json(args.pool), model_key=args.model, split=args.split, endpoint=endpoint),
    )


def _load_runs(paths: list[str]) -> list[dict[str, Any]]:
    """Accept either one run per file or the list of runs `pool` writes."""
    runs: list[dict[str, Any]] = []
    for path in paths:
        loaded = load_json(path)
        if isinstance(loaded, list):
            if any(not isinstance(row, dict) for row in loaded):
                raise EvalError(f"{path} must hold a run object or a list of them")
            runs.extend(loaded)
        elif isinstance(loaded, dict):
            runs.append(loaded)
        else:
            raise EvalError(f"{path} must hold a run object or a list of them")
    return runs


def _cmd_fuse(args: argparse.Namespace) -> None:
    write_json(args.output, rank_fusion(_load_runs(args.runs), constant=args.constant))


def _cmd_review(args: argparse.Namespace) -> None:
    rows = review_sheet(load_json(args.pool), seed=args.seed, max_chars=args.max_chars)
    write_review_sheet(args.output, rows)
    if not rows:
        raise EvalError("the pool has no candidates to review")


def _cmd_qrels(args: argparse.Namespace) -> None:
    qrels = qrels_from_review(
        args.review,
        load_json(args.pool),
        qrels_version=args.version,
        require_complete=not args.allow_partial,
    )
    write_json(args.output, qrels, immutable=True)


def _cmd_compare(args: argparse.Namespace) -> None:
    runs = _load_runs(args.runs)
    if len(runs) != 2:
        raise EvalError(f"comparison needs exactly two runs, found {len(runs)}")
    write_json(
        args.output,
        compare_runs(
            runs[0],
            runs[1],
            load_json(args.pool),
            load_json(args.qrels),
            split=args.split,
            resamples=args.resamples,
            seed=args.seed,
        ),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture and evaluate retrieval runs offline.")
    commands = parser.add_subparsers(dest="command", required=True)
    cap = commands.add_parser("capture", help="capture one engine arm to a new immutable JSON artifact")
    cap.add_argument("--questions", required=True)
    cap.add_argument("--output", required=True)
    cap.add_argument("--graph", choices=("on", "off"), required=True)
    cap.add_argument("--k", type=int, default=50)
    cap.add_argument("--rerank", choices=("on", "off"), default="off")
    cap.add_argument("--rerank-k", type=int, default=30)
    cap.set_defaults(
        func=lambda args: capture(
            args.questions,
            args.output,
            graph=args.graph == "on",
            k=args.k,
            rerank=args.rerank == "on",
            rerank_k=args.rerank_k,
        )
    )
    questions = commands.add_parser("questions", help="validate split sizes before an immutable capture")
    questions.add_argument("--questions", required=True)
    questions.add_argument("--output")
    questions.set_defaults(func=_cmd_questions)
    pool = commands.add_parser("pool", help="build a blinded union pool and retrieval rankings")
    pool.add_argument("--captures", nargs="+", required=True)
    pool.add_argument("--pool", required=True)
    pool.add_argument("--mapping", required=True)
    pool.add_argument("--runs", required=True)
    pool.set_defaults(func=_cmd_pool)
    gliner = commands.add_parser("gliner", help="rerank the blinded pool with GLiNER2, locally or over an endpoint")
    gliner.add_argument("--pool", required=True)
    gliner.add_argument("--model", choices=tuple(MODEL_PINS), default="decide")
    gliner.add_argument("--split", choices=("development", "test"), default="development")
    gliner.add_argument("--endpoint", help="GLiNER2 API base URL, e.g. the machine serving the model")
    gliner.add_argument("--local", action="store_true", help="load the pinned model here instead of an endpoint")
    gliner.add_argument("--output", required=True)
    gliner.set_defaults(func=_cmd_gliner)
    fuse = commands.add_parser("fuse", help="combine captured rankings with reciprocal rank fusion")
    fuse.add_argument("--runs", nargs="+", required=True)
    fuse.add_argument("--constant", type=int, default=60)
    fuse.add_argument("--output", required=True)
    fuse.set_defaults(func=_cmd_fuse)
    score = commands.add_parser("score", help="score fully judged queries with retrieval metrics")
    score.add_argument("--run", required=True)
    score.add_argument("--run-id", help="which arm to score when the file holds several")
    score.add_argument("--pool", required=True)
    score.add_argument("--qrels", required=True)
    score.add_argument("--split", choices=("development", "test"))
    score.add_argument("--for-selection", action="store_true")
    score.add_argument("--output", required=True)
    score.set_defaults(func=_cmd_score)
    review = commands.add_parser("review", help="write a blinded review sheet with no ranks or system names")
    review.add_argument("--pool", required=True)
    review.add_argument("--output", required=True)
    review.add_argument("--seed", type=int, default=0)
    review.add_argument("--max-chars", type=int, default=1200)
    review.set_defaults(func=_cmd_review)
    qrels = commands.add_parser("qrels", help="build qrels from a reviewed sheet")
    qrels.add_argument("--review", required=True)
    qrels.add_argument("--pool", required=True)
    qrels.add_argument("--version", required=True)
    qrels.add_argument("--allow-partial", action="store_true")
    qrels.add_argument("--output", required=True)
    qrels.set_defaults(func=_cmd_qrels)
    compare = commands.add_parser("compare", help="paired bootstrap intervals between two runs")
    compare.add_argument("--runs", nargs="+", required=True)
    compare.add_argument("--pool", required=True)
    compare.add_argument("--qrels", required=True)
    compare.add_argument("--split", choices=("development", "test"))
    compare.add_argument("--resamples", type=int, default=2000)
    compare.add_argument("--seed", type=int, default=0)
    compare.add_argument("--output", required=True)
    compare.set_defaults(func=_cmd_compare)
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EvalError as exc:
        print(f"retrieval-eval: {exc}", file=sys.stderr)
        raise SystemExit(2)
