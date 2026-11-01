import json

import pytest

from tools import retrieval_eval


def _capture(qid, results, added=None, split="development"):
    return {
        "run_id": "arm-a",
        "config": {"graph": bool(added), "rerank": False, "k": 50},
        "queries": [
            {
                "id": qid,
                "question": "Which authority controls?",
                "split": split,
                "response": {
                    "stages": [{"stage": "graph", "added": added or [], "graph_revision": "g1"}],
                    "result": {
                        "corpus_revision": "c1",
                        "graph_revision": "g1",
                        "results": results,
                    },
                },
            }
        ],
    }


def _row(case_id, text, rank, score):
    return {
        "rank": rank,
        "score": score,
        "case": {"id": case_id, "name": case_id},
        "passages": [{"chunk_id": case_id + "-p1", "text": text}],
        "provenance": [{"source": "hybrid"}],
    }


def test_capture_rows_require_known_engine_contract():
    response = {"result": {"results": [_row("A v. B", "passage", 1, 0.9)]}}
    candidates = retrieval_eval.extract_candidates("q1", response)
    assert candidates[0]["document_key"] == "A v. B"
    assert candidates[0]["text"] == "passage"
    assert candidates[0]["raw"]["provenance"][0]["source"] == "hybrid"
    with pytest.raises(retrieval_eval.EvalError, match="result.results"):
        retrieval_eval.extract_candidates("q1", {"result": {"items": []}})


def test_pool_deduplicates_across_arms_and_blinds_ids():
    row_a = _row("A v. B", "same passage", 1, 0.9)
    row_b = _row("A v. B", "same passage", 2, 0.7)
    captures = [
        _capture("q1", [row_a]),
        _capture("q1", [row_b], [{"doc_id": "Ghost v. State"}]),
    ]
    pool, mapping, runs = retrieval_eval.build_pool(captures)
    assert len(pool["documents"]) == 1
    opaque = pool["documents"][0]["opaque_id"]
    assert opaque != "A v. B"
    assert mapping[opaque]["document_key"] == "A v. B"
    assert set(mapping[opaque]["arms"]) == {"arm-a"}
    assert runs[0]["queries"]["q1"][0]["doc_id"] == opaque
    # An addition the graph reported but that never reached the results is a finding, not a defect:
    # it is recorded so starvation is visible, and the capture still scores.
    assert captures[1]["queries"][0]["capture_complete"] is True
    assert captures[1]["queries"][0]["candidate_completeness"]["graph_added_not_returned"] == ["Ghost v. State"]


def test_metrics_are_withheld_until_every_pooled_document_is_judged():
    pool = {
        "questions": [{"id": "q1", "split": "development"}],
        "documents": [
            {"query_id": "q1", "opaque_id": "a"},
            {"query_id": "q1", "opaque_id": "b"},
        ],
    }
    run = {"run_id": "r", "queries": {"q1": [{"doc_id": "a", "score": 2.0}, {"doc_id": "b", "score": 1.0}]}}
    partial = {"judgments": [{"query_id": "q1", "opaque_id": "a", "grade": 2}]}
    report = retrieval_eval.score_run(run, pool, partial)
    assert report["queries"]["q1"]["metrics"] is None
    assert report["queries"]["q1"]["label_coverage"] == 0.5


def test_scoring_uses_three_grade_qrels_and_known_relevant_recall():
    pool = {
        "questions": [{"id": "q1", "split": "development"}],
        "documents": [
            {"query_id": "q1", "opaque_id": "a"},
            {"query_id": "q1", "opaque_id": "b"},
            {"query_id": "q1", "opaque_id": "c"},
        ],
    }
    run = {"run_id": "r", "queries": {"q1": [{"doc_id": "a", "score": 3.0}, {"doc_id": "b", "score": 2.0}]}}
    qrels = {
        "judgments": [
            {"query_id": "q1", "opaque_id": "a", "grade": 2},
            {"query_id": "q1", "opaque_id": "b", "grade": 1},
            {"query_id": "q1", "opaque_id": "c", "grade": 0},
        ]
    }
    metrics = retrieval_eval.score_run(run, pool, qrels)["queries"]["q1"]["metrics"]
    assert metrics["precision@3"] == pytest.approx(2 / 3)
    assert metrics["precision@10"] == pytest.approx(0.2)
    assert metrics["known_relevant_recall@10"] == 1.0
    assert metrics["ndcg@10"] <= 1.0


def test_test_split_cannot_be_used_to_select_a_configuration():
    with pytest.raises(retrieval_eval.EvalError, match="development"):
        retrieval_eval.assert_selection_split("test")
    retrieval_eval.assert_selection_split("development")


def _engine_row(case_id, name, text, provenance, rank=1, score=1.0):
    """One `result.results[]` row in the shape app/octo_retriever.py::_from_engine consumes."""
    return {
        "rank": rank,
        "score": score,
        "case": {"id": case_id, "name": name, "court": "Colo. App.", "year": 1995},
        "passages": [{"chunk_id": case_id + "-p1", "text": text}],
        "provenance": [{"source": source} for source in provenance],
    }


def _engine_response(rows, added=None, graph_skipped=False, frontier=None, edges_scanned=None):
    """The stage record the engine actually sends: `stage`, not `name`, plus graph additions."""
    stage = {"stage": "graph", "duration_ms": 94.7, "skipped": graph_skipped}
    if added is not None:
        stage["added"] = [{"doc_id": doc_id} for doc_id in added]
    if frontier is not None:
        stage["frontier"] = frontier
    if edges_scanned is not None:
        stage["edges_scanned"] = edges_scanned
    return {"stages": [stage], "result": {"results": rows, "corpus_revision": "c1"}}


def test_opaque_engine_row_id_never_becomes_the_pool_key():
    # The engine keys some cases by an opaque row id; the app swaps in the name a reader can check.
    row = _engine_row("1:2345", "People v. Lee, 914 P.2d 441", "text", ["bm25"])
    candidates = retrieval_eval.extract_candidates("q1", _engine_response([row]))
    assert candidates[0]["document_key"] == "People v. Lee, 914 P.2d 441"


def test_named_case_id_is_kept_as_the_pool_key():
    row = _engine_row("People v. Lee", "People v. Lee, 914 P.2d 441", "text", ["dense"])
    candidates = retrieval_eval.extract_candidates("q1", _engine_response([row]))
    assert candidates[0]["document_key"] == "People v. Lee"


def test_graph_only_candidate_comes_from_the_graph_stage_additions():
    # Provenance on a real result row only ever names bm25/dense, so the additions list is the signal.
    rows = [
        _engine_row("A v. B", "A v. B", "hybrid passage", ["bm25", "dense"]),
        _engine_row("C v. D", "C v. D", "graph passage", ["graph"], rank=2),
    ]
    response = _engine_response(rows, added=["C v. D"], frontier=["A v. B"], edges_scanned=11)
    candidates = retrieval_eval.extract_candidates("q1", response)
    quality = retrieval_eval._completeness(response, candidates, {"graph": True, "k": 50})
    assert [candidate["graph_only"] for candidate in candidates] == [False, True]
    assert quality["graph_only_candidates"] == ["C v. D"]
    assert quality["stage_attribution_available"] is True
    assert quality["graph_additions_reported"] is True
    assert quality["graph_edges_scanned"] == 11
    assert quality["graph_frontier_size"] == 1


def test_a_graph_addition_that_never_returns_is_reported_not_fatal():
    rows = [_engine_row("A v. B", "A v. B", "text", ["bm25"])]
    response = _engine_response(rows, added=["Starved v. State"])
    candidates = retrieval_eval.extract_candidates("q1", response)
    quality = retrieval_eval._completeness(response, candidates, {"graph": True, "k": 50})
    assert quality["graph_added_count"] == 1
    assert quality["graph_added_not_returned"] == ["Starved v. State"]
    assert quality["candidate_pool_complete"] is True


def test_capture_without_provenance_fails_the_attribution_gate():
    # A row with no provenance must not count as a hybrid hit.
    row = _engine_row("A v. B", "A v. B", "text", [])
    candidates = retrieval_eval.extract_candidates("q1", _engine_response([row]))
    quality = retrieval_eval._completeness(_engine_response([row]), candidates, {"graph": True, "k": 50})
    assert quality["candidate_pool_complete"] is False
    assert quality["stage_attribution_available"] is False


def test_truncated_pool_is_disclosed_without_blocking_attribution():
    row = _engine_row("A v. B", "A v. B", "text", ["bm25"])
    candidates = retrieval_eval.extract_candidates("q1", _engine_response([row]))
    quality = retrieval_eval._completeness(_engine_response([row]), candidates, {"graph": True, "k": 50, "bm25_k": 100, "dense_pool": 100})
    assert quality["pool_truncated_by_k"] is True
    assert quality["stage_attribution_available"] is True
    assert quality["candidate_pool_complete"] is True


def test_provenance_reaches_the_run_but_not_the_blinded_pool():
    row = _engine_row("C v. D", "C v. D", "graph passage", ["graph"])
    pool, _mapping, runs = retrieval_eval.build_pool([_capture("q1", [row], [{"doc_id": "C v. D"}])])
    assert runs[0]["queries"]["q1"][0]["graph_only"] is True
    assert runs[0]["queries"]["q1"][0]["provenance"] == ["graph"]
    assert "provenance" not in pool["documents"][0]


def test_fuse_accepts_the_run_list_that_pool_writes(monkeypatch):
    # `pool` writes runs.json as a list; `fuse` used to require one run per file and could not read it.
    row = _engine_row("A v. B", "A v. B", "text", ["bm25"])
    _pool, _mapping, runs = retrieval_eval.build_pool([_capture("q1", [row])])
    monkeypatch.setattr(retrieval_eval, "load_json", lambda path: runs)
    assert [run["run_id"] for run in retrieval_eval._load_runs(["runs.json"])] == ["arm-a"]


def test_fuse_combines_two_pooled_runs():
    first = _capture("q1", [_engine_row("A v. B", "A v. B", "text", ["bm25"])])
    second = _capture("q1", [_engine_row("A v. B", "A v. B", "text", ["dense"])])
    second["run_id"] = "arm-b"
    _pool, _mapping, runs = retrieval_eval.build_pool([first, second])
    fused = retrieval_eval.rank_fusion(runs)
    assert fused["run_id"] == "rrf-arm-a+arm-b"
    assert len(fused["queries"]["q1"]) == 1


def test_question_labels_survive_normalization():
    normalized = retrieval_eval.normalize_questions(
        {
            "questions": [
                {
                    "id": "q1",
                    "question": "Who holds the water right?",
                    "split": "development",
                    "topic": "water_rights",
                    "answerability_expectation": "no_answer_expected",
                }
            ]
        }
    )
    assert normalized[0]["topic"] == "water_rights"
    assert normalized[0]["answerability_expectation"] == "no_answer_expected"


def test_scores_break_down_by_topic_and_answerability():
    pool = {
        "questions": [
            {"id": "q1", "split": "development", "topic": "water_rights", "answerability_expectation": "answerable_expected"},
            {"id": "q2", "split": "development", "topic": "property", "answerability_expectation": "answerable_expected"},
        ],
        "documents": [
            {"query_id": "q1", "opaque_id": "a"},
            {"query_id": "q2", "opaque_id": "b"},
        ],
    }
    run = {"run_id": "r", "queries": {"q1": [{"doc_id": "a"}], "q2": [{"doc_id": "b"}]}}
    qrels = {
        "judgments": [
            {"query_id": "q1", "opaque_id": "a", "grade": 2},
            {"query_id": "q2", "opaque_id": "b", "grade": 0},
        ]
    }
    report = retrieval_eval.score_run(run, pool, qrels)
    topics = report["breakdowns"]["topic"]
    assert topics["water_rights"]["macro_metrics"]["ndcg@10"] == 1.0
    assert topics["property"]["macro_metrics"]["ndcg@10"] == 0.0
    assert report["breakdowns"]["answerability_expectation"]["answerable_expected"]["scored_query_count"] == 2


def test_dataset_validation_accepts_matching_counts():
    data = {
        "questions": [
            {"id": "d1", "question": "q", "split": "development", "topic": "water_rights", "group_id": "g1"},
            {"id": "t1", "question": "q", "split": "test", "topic": "water_rights", "group_id": "g2"},
        ]
    }
    report = retrieval_eval.validate_dataset(data, development=1, test=1, development_per_topic=1, test_per_topic=1)
    assert report["ok"] is True
    assert report["by_topic"]["water_rights"] == {"development": 1, "test": 1}


def test_dataset_validation_flags_a_group_crossing_the_split():
    data = {
        "questions": [
            {"id": "d1", "question": "q", "split": "development", "topic": "water_rights", "group_id": "shared"},
            {"id": "t1", "question": "q", "split": "test", "topic": "water_rights", "group_id": "shared"},
        ]
    }
    report = retrieval_eval.validate_dataset(data, development=1, test=1, development_per_topic=1, test_per_topic=1)
    assert report["ok"] is False
    assert any("cross the split" in problem for problem in report["problems"])


def test_dataset_validation_flags_a_topic_with_the_wrong_count():
    data = {"questions": [{"id": "d1", "question": "q", "split": "development", "topic": "property"}]}
    report = retrieval_eval.validate_dataset(data, development=1, test=0, development_per_topic=5, test_per_topic=0)
    assert report["ok"] is False
    assert any("property" in problem for problem in report["problems"])


@pytest.fixture
def sheet_dir():
    import pathlib
    import shutil
    import tempfile

    path = pathlib.Path(tempfile.mkdtemp())
    yield path
    shutil.rmtree(path, ignore_errors=True)


def _review_pool():
    return {
        "questions": [{"id": "q1", "question": "Which authority controls?", "split": "development", "topic": "water_rights"}],
        "documents": [
            {"query_id": "q1", "opaque_id": "a", "text": "alpha passage"},
            {"query_id": "q1", "opaque_id": "b", "text": "beta passage"},
        ],
    }


def test_review_sheet_carries_no_rank_or_system_opinion():
    rows = retrieval_eval.review_sheet(_review_pool(), seed=3)
    assert set(rows[0]) == set(retrieval_eval.REVIEW_COLUMNS)
    assert all(row["grade"] == "" for row in rows)
    assert {row["document_id"] for row in rows} == {"a", "b"}
    assert rows[0]["question"] == "Which authority controls?"


def test_review_sheet_order_is_reproducible():
    first = [row["document_id"] for row in retrieval_eval.review_sheet(_review_pool(), seed=7)]
    second = [row["document_id"] for row in retrieval_eval.review_sheet(_review_pool(), seed=7)]
    assert first == second


def test_qrels_round_trip_from_a_reviewed_sheet(sheet_dir):
    pool = _review_pool()
    rows = retrieval_eval.review_sheet(pool)
    grades = {"a": "2", "b": "0"}
    for row in rows:
        row["grade"] = grades[row["document_id"]]
        row["reviewer"] = "reviewer-1"
    path = sheet_dir / "sheet.csv"
    retrieval_eval.write_review_sheet(path, rows)
    qrels = retrieval_eval.qrels_from_review(path, pool, qrels_version="v1")
    assert qrels["judged_candidates"] == 2
    assert qrels["label_coverage"] == 1.0
    assert qrels["reviewers"] == ["reviewer-1"]
    assert {j["opaque_id"]: j["grade"] for j in qrels["judgments"]} == {"a": 2, "b": 0}


def test_qrels_refuse_an_ungraded_row_unless_partial_is_allowed(sheet_dir):
    pool = _review_pool()
    rows = retrieval_eval.review_sheet(pool)
    for row in rows:
        row["grade"] = "2" if row["document_id"] == "a" else ""
    path = sheet_dir / "sheet.csv"
    retrieval_eval.write_review_sheet(path, rows)
    with pytest.raises(retrieval_eval.EvalError, match="no grade"):
        retrieval_eval.qrels_from_review(path, pool, qrels_version="v1")
    partial = retrieval_eval.qrels_from_review(path, pool, qrels_version="v1", require_complete=False)
    assert partial["label_coverage"] == 0.5


def test_qrels_refuse_a_document_outside_the_pool(sheet_dir):
    pool = _review_pool()
    rows = retrieval_eval.review_sheet(pool)
    for row in rows:
        row["grade"] = "1"
    rows[0]["document_id"] = "not-in-pool"
    path = sheet_dir / "sheet.csv"
    retrieval_eval.write_review_sheet(path, rows)
    with pytest.raises(retrieval_eval.EvalError, match="not in the blinded pool"):
        retrieval_eval.qrels_from_review(path, pool, qrels_version="v1")


def _compare_fixture():
    pool = {
        "questions": [
            {"id": "q1", "split": "development", "topic": "water_rights"},
            {"id": "q2", "split": "development", "topic": "property"},
        ],
        "documents": [
            {"query_id": "q1", "opaque_id": "a"},
            {"query_id": "q1", "opaque_id": "b"},
            {"query_id": "q2", "opaque_id": "c"},
            {"query_id": "q2", "opaque_id": "d"},
        ],
    }
    qrels = {
        "judgments": [
            {"query_id": "q1", "opaque_id": "a", "grade": 2},
            {"query_id": "q1", "opaque_id": "b", "grade": 0},
            {"query_id": "q2", "opaque_id": "c", "grade": 2},
            {"query_id": "q2", "opaque_id": "d", "grade": 0},
        ]
    }
    good = {"run_id": "good", "queries": {"q1": [{"doc_id": "a"}, {"doc_id": "b"}], "q2": [{"doc_id": "c"}, {"doc_id": "d"}]}}
    bad = {"run_id": "bad", "queries": {"q1": [{"doc_id": "b"}, {"doc_id": "a"}], "q2": [{"doc_id": "d"}, {"doc_id": "c"}]}}
    return pool, qrels, good, bad


def test_compare_identical_runs_is_inconclusive():
    pool, qrels, good, _bad = _compare_fixture()
    report = retrieval_eval.compare_runs(good, good, pool, qrels, resamples=200)
    assert report["paired_query_count"] == 2
    assert report["separates_arms"] is False
    assert report["inconclusive"] is True
    assert report["metrics"]["ndcg@10"]["observed_difference"] == 0.0


def test_compare_separates_a_clearly_better_run():
    pool, qrels, good, bad = _compare_fixture()
    report = retrieval_eval.compare_runs(good, bad, pool, qrels, resamples=200, seed=1)
    ndcg = report["metrics"]["ndcg@10"]
    assert ndcg["observed_difference"] > 0
    assert ndcg["separates_arms"] is True
    assert report["inconclusive"] is False


def test_pool_records_the_corpus_revision_it_was_built_from():
    row = _engine_row("A v. B", "A v. B", "text", ["bm25"])
    capture = _capture("q1", [row])
    capture["queries"][0]["response"]["result"]["corpus_revision"] = "octo-chunk:804646"
    pool, _mapping, _runs = retrieval_eval.build_pool([capture])
    assert pool["corpus_revision"] == "octo-chunk:804646"


def test_pool_refuses_arms_captured_on_different_corpus_revisions():
    # Two arms taken either side of a reindex are not a comparison; the corpus moved under them.
    row = _engine_row("A v. B", "A v. B", "text", ["bm25"])
    first = _capture("q1", [row])
    first["queries"][0]["response"]["result"]["corpus_revision"] = "octo-chunk:804646"
    second = _capture("q1", [row])
    second["run_id"] = "arm-b"
    second["queries"][0]["response"]["result"]["corpus_revision"] = "octo-chunk:812300"
    with pytest.raises(retrieval_eval.EvalError, match="corpus changed between arms"):
        retrieval_eval.build_pool([first, second])


def _graph_pool_run():
    pool = {
        "questions": [{"id": "q1", "split": "development"}],
        "documents": [
            {"query_id": "q1", "opaque_id": "a"},
            {"query_id": "q1", "opaque_id": "b"},
            {"query_id": "q1", "opaque_id": "c"},
        ],
    }
    run = {
        "run_id": "graph-arm",
        "queries": {
            "q1": [
                {"doc_id": "a", "provenance": ["bm25"], "graph_only": False},
                {"doc_id": "b", "provenance": ["graph"], "graph_only": True},
                {"doc_id": "c", "provenance": ["graph"], "graph_only": True},
            ]
        },
    }
    qrels = {
        "judgments": [
            {"query_id": "q1", "opaque_id": "a", "grade": 1},
            {"query_id": "q1", "opaque_id": "b", "grade": 2},
            {"query_id": "q1", "opaque_id": "c", "grade": 0},
        ]
    }
    return pool, run, qrels


def test_graph_contribution_counts_only_graph_only_relevant_candidates():
    pool, run, qrels = _graph_pool_run()
    report = retrieval_eval.score_run(run, pool, qrels)
    contribution = report["queries"]["q1"]["graph_contribution"]
    assert contribution["graph_only_candidates"] == 2
    assert contribution["graph_only_relevant"] == 1
    assert contribution["graph_only_relevant_in_top3"] == 1
    assert contribution["graph_only_relevant_in_top10"] == 1
    assert report["graph_contribution_totals"]["graph_only_relevant"] == 1


def test_graph_contribution_is_withheld_with_the_metrics():
    pool, run, qrels = _graph_pool_run()
    qrels["judgments"] = qrels["judgments"][:2]
    report = retrieval_eval.score_run(run, pool, qrels)
    assert report["queries"]["q1"]["metrics"] is None
    assert report["queries"]["q1"]["graph_contribution"] is None
    assert report["graph_contribution_totals"] is None


def test_model_pins_are_full_commit_shas():
    for key, (_model_id, revision) in retrieval_eval.MODEL_PINS.items():
        assert len(revision) == 40, f"{key} pin is not a full commit sha"
        assert all(character in "0123456789abcdef" for character in revision), key


def test_confidence_maps_labels_and_tolerates_an_unlabelled_passage():
    assert retrieval_eval._confidence({"relevance": {"label": "yes", "confidence": 0.9}}) == 0.9
    assert retrieval_eval._confidence({"relevance": {"label": "no", "confidence": 0.8}}) == pytest.approx(0.2)
    assert retrieval_eval._confidence({"relevance": None}) == 0.0
    assert retrieval_eval._confidence({"relevance": {}}) == 0.0
    assert retrieval_eval._confidence({}) == 0.0
    with pytest.raises(retrieval_eval.EvalError, match="label with a confidence"):
        retrieval_eval._confidence({"relevance": "yes"})
    with pytest.raises(retrieval_eval.EvalError, match="yes/no label"):
        retrieval_eval._confidence({"relevance": {"label": "maybe", "confidence": 0.5}})


def test_gliner_rerank_pins_the_model_and_orders_by_confidence(monkeypatch):
    import sys
    import types

    seen = {}

    class FakeExtractor:
        @classmethod
        def from_pretrained(cls, model_id, revision=None):
            seen["pin"] = (model_id, revision)
            return cls()

        def classify_text(self, text, tasks, **kwargs):
            seen["threshold"] = kwargs.get("threshold")
            confidence = 0.9 if "alpha" in text else 0.2
            return {"relevance": {"label": "yes", "confidence": confidence}}

    module = types.ModuleType("gliner2")
    module.AutoExtractor = FakeExtractor
    monkeypatch.setitem(sys.modules, "gliner2", module)

    pool = {
        "questions": [{"id": "q1", "question": "Which authority?", "split": "development"}],
        "documents": [
            {"query_id": "q1", "opaque_id": "a", "text": "alpha passage"},
            {"query_id": "q1", "opaque_id": "b", "text": "beta passage"},
        ],
    }
    run = retrieval_eval.gliner_rerank(pool, model_key="decide")
    assert [row["doc_id"] for row in run["queries"]["q1"]] == ["a", "b"]
    assert run["queries"]["q1"][0]["score"] == 0.9
    assert run["revision"] == retrieval_eval.MODEL_PINS["decide"][1]
    assert seen["pin"] == retrieval_eval.MODEL_PINS["decide"]
    assert seen["threshold"] == 0.0


def _gliner_pool():
    return {
        "questions": [{"id": "q1", "question": "Which authority?", "split": "development"}],
        "documents": [
            {"query_id": "q1", "opaque_id": "a", "text": "alpha passage"},
            {"query_id": "q1", "opaque_id": "b", "text": "beta passage"},
        ],
    }


def test_gliner_over_an_endpoint_does_not_claim_a_pin(monkeypatch):
    import sys
    import types

    seen = {}

    class FakeAPI:
        def __init__(self, api_key=None, api_base_url=None):
            seen["key"] = api_key
            seen["base"] = api_base_url

        def classify_text(self, text, tasks, **kwargs):
            seen["threshold"] = kwargs.get("threshold")
            return {"relevance": {"label": "yes", "confidence": 0.7}}

    module = types.ModuleType("gliner2")
    module.GLiNER2API = FakeAPI
    monkeypatch.setitem(sys.modules, "gliner2", module)
    monkeypatch.setenv("FASTINO_API_KEY", "test-key")

    run = retrieval_eval.gliner_rerank(_gliner_pool(), endpoint="http://windows-box:8080")
    assert run["mode"] == "remote"
    assert run["client"] == "sdk"
    assert run["model_pin_enforced"] is False
    assert run["endpoint"] == "http://windows-box:8080"
    assert run["revision"] is None
    assert seen["base"] == "http://windows-box:8080"
    assert seen["threshold"] == 0.0
    assert run["queries"]["q1"][0]["score"] == 0.7


def test_gliner_endpoint_falls_back_to_the_documented_contract(monkeypatch):
    import sys

    sent = {}

    class FakeResponse:
        def __init__(self, body):
            self.body = body

        def read(self):
            return json.dumps(self.body).encode()

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(request, timeout=None):
        sent["url"] = request.full_url
        sent["headers"] = dict(request.headers)
        sent["payload"] = json.loads(request.data)
        return FakeResponse({"classification": {"label": "yes", "confidence": 0.66}})

    monkeypatch.setitem(sys.modules, "gliner2", None)
    monkeypatch.setenv("GLINER2_API_KEY", "test-key")
    monkeypatch.setattr(retrieval_eval.urllib.request, "urlopen", fake_urlopen)

    run = retrieval_eval.gliner_rerank(_gliner_pool(), endpoint="http://windows-box:8080/")
    assert run["client"] == "http"
    assert run["queries"]["q1"][0]["score"] == 0.66
    assert sent["url"] == "http://windows-box:8080/gliner-2"
    assert sent["payload"]["threshold"] == 0.0
    assert sent["payload"]["task"] == "classify_text"
    assert sent["payload"]["include_confidence"] is True


def test_gliner_endpoint_requires_a_key(monkeypatch):
    monkeypatch.delenv("FASTINO_API_KEY", raising=False)
    monkeypatch.delenv("GLINER2_API_KEY", raising=False)
    with pytest.raises(retrieval_eval.EvalError, match="FASTINO_API_KEY"):
        retrieval_eval._gliner_client(model_key="decide", endpoint="http://windows-box:8080", api_key=None)


def test_frozen_artifact_is_never_overwritten(sheet_dir):
    path = sheet_dir / "frozen.json"
    retrieval_eval.write_json(path, {"a": 1}, immutable=True)
    with pytest.raises(retrieval_eval.EvalError, match="never overwritten"):
        retrieval_eval.write_json(path, {"a": 2}, immutable=True)
    assert retrieval_eval.load_json(path) == {"a": 1}


def test_score_command_refuses_a_file_holding_two_runs(monkeypatch):
    import argparse

    runs = [{"run_id": "a", "queries": {}}, {"run_id": "b", "queries": {}}]
    monkeypatch.setattr(retrieval_eval, "load_json", lambda path: runs)
    args = argparse.Namespace(run="runs.json", run_id=None, pool="p", qrels="q", split=None, for_selection=False, output="o")
    with pytest.raises(retrieval_eval.EvalError, match="one arm at a time"):
        retrieval_eval._cmd_score(args)


def test_percentile_interpolates_and_handles_empty():
    assert retrieval_eval._percentile([], 0.5) is None
    assert retrieval_eval._percentile([10.0], 0.95) == 10.0
    assert retrieval_eval._percentile([0.0, 10.0], 0.5) == 5.0
    assert retrieval_eval._percentile([0.0, 10.0], 0.95) == pytest.approx(9.5)
