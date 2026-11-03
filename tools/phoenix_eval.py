"""Run the `precedent-legal` cases through the pipeline and record the result as a Phoenix experiment (#64).

    PHOENIX_URL=http://<phoenix>:6006 PHOENIX_SECRET=... python tools/phoenix_eval.py --dataset precedent-legal --name baseline

Creates the dataset in Phoenix when it does not exist, runs each case, scores it with the code evaluators
below, and posts the runs and scores to Phoenix so experiments are comparable side by side. The pipeline
call is the same one the site makes; run it on a copy of the app (`RUNS_KEPT` high, `OCTO_TRACES=off`) so it
does not push real runs out of the store or put experiment traces in the `legal-graph-rag` project.
"""

import argparse
import datetime as dt
import os
import re
import sys

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.phoenix_cases import DATASETS  # noqa: E402


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _text(cite):
    return f"{cite.get('title') or ''} {cite.get('passage') or ''}"


def evaluate(case, output):
    """{name: {label, score, explanation}} for one case. Pure: no network, no model."""
    from app.agents import NO_AUTHORITY

    cites = [c for c in output.get("citations") or [] if c.get("ref")]
    refused = (output.get("answer") or "").strip() == NO_AUTHORITY.strip()
    scores = {}
    if case["expect"] == "no_authority":
        scores["refuses_off_topic"] = _score(refused, "refused" if refused else "answered", "an off-topic question must get the no-authority answer")
        return scores
    scores["answers_on_topic"] = _score(not refused, "answered" if not refused else "refused", "an on-topic question must not be refused")
    topic = re.compile(case["topic"], re.I)
    on = [c for c in cites if topic.search(_text(c))]
    share = len(on) / len(cites) if cites else 0.0
    scores["on_topic_citations"] = {
        "label": "pass" if cites and share >= 0.5 else "fail",
        "score": round(share, 3),
        "explanation": f"{len(on)} of {len(cites)} cited authorities mention the subject",
    }
    if case.get("must_not_cite"):
        wrong = re.compile(case["must_not_cite"], re.I)
        # An authority on the subject that merely mentions "theater" in passing is not a wrong-subject citation.
        bad = [c.get("title") for c in cites if wrong.search(_text(c)) and not topic.search(_text(c))]
        scores["no_wrong_subject_citations"] = _score(not bad, "clean" if not bad else "wrong-subject", f"cited: {bad[:5]}" if bad else "none matched")
    sg = output.get("safeguard") or {}
    support = sg.get("support") or {}
    scores["support_check"] = _score(
        bool(support.get("ran")) and not support.get("abstain"),
        "supported" if support.get("ran") and not support.get("abstain") else "abstained",
        f"confidence={support.get('answer_confidence')}",
    )
    scores["citation_guard"] = _score(
        bool(sg.get("regex_pass")), "pass" if sg.get("regex_pass") else "fail", f"invalid={sg.get('invalid')} unknown={sg.get('unknown_authorities')}"
    )
    return scores


def _score(ok, label, explanation):
    return {"label": label, "score": 1.0 if ok else 0.0, "explanation": explanation}


def run_case(case, pipeline):
    """Ask the history in order, then the case question as a follow-up of the last answer. Returns the output record."""
    prev = None
    for question in case.get("history") or []:
        prev = pipeline(question, prev)
    result = pipeline(case["question"], prev)
    return {
        "answer": result.get("answer"),
        "coverage": result.get("coverage"),
        "provider": result.get("provider"),
        "standalone_query": result.get("standalone_query"),
        "citations": [{k: c.get(k) for k in ("ref", "title", "passage", "score")} for c in result.get("citations") or []],
        "safeguard": result.get("safeguard"),
    }


class Phoenix:
    def __init__(self, base, secret):
        self.http = httpx.Client(base_url=base.rstrip("/"), headers={"Authorization": f"Bearer {secret}"}, timeout=60)

    def _json(self, method, path, **kw):
        r = self.http.request(method, path, **kw)
        r.raise_for_status()
        return r.json()["data"]

    def dataset(self, name, description, cases):
        for d in self._json("GET", "/v1/datasets", params={"name": name}):
            if d["name"] == name:
                return d["id"]
        body = {
            "action": "create",
            "name": name,
            "description": description,
            "inputs": [{"question": c["question"], "history": c.get("history") or []} for c in cases],
            "outputs": [{"expect": c["expect"], "topic": c.get("topic"), "must_not_cite": c.get("must_not_cite")} for c in cases],
            "metadata": [{"case_id": c["id"]} for c in cases],
        }
        return self._json("POST", "/v1/datasets/upload", params={"sync": "true"}, json=body)["dataset_id"]

    def examples(self, dataset_id):
        data = self._json("GET", f"/v1/datasets/{dataset_id}/examples")
        return data["version_id"], data["examples"]

    def experiment(self, dataset_id, version_id, name, description, metadata):
        return self._json(
            "POST",
            f"/v1/datasets/{dataset_id}/experiments",
            json={"name": name, "description": description, "metadata": metadata, "version_id": version_id, "repetitions": 1},
        )["id"]

    def record(self, experiment_id, example_id, output, started, ended, scores):
        run_id = self._json(
            "POST",
            f"/v1/experiments/{experiment_id}/runs",
            json={"dataset_example_id": example_id, "output": output, "repetition_number": 1, "start_time": started, "end_time": ended},
        )["id"]
        for name, result in scores.items():
            self.http.post(
                "/v1/experiment_evaluations",
                json={"experiment_run_id": run_id, "name": name, "annotator_kind": "CODE", "start_time": started, "end_time": _now(), "result": result},
            ).raise_for_status()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=sorted(DATASETS), default="precedent-legal")
    ap.add_argument("--name", required=True, help="experiment name, e.g. baseline or pr-62")
    ap.add_argument("--description", default="")
    ap.add_argument("--only", help="run only the case ids containing this text")
    ap.add_argument("--judges", action="store_true", help="also score each answer with the four LLM judges (one model call each)")
    args = ap.parse_args(argv)
    from app import agents

    phoenix = Phoenix(os.environ["PHOENIX_URL"], os.environ["PHOENIX_SECRET"])
    description, cases = DATASETS[args.dataset]
    dataset_id = phoenix.dataset(args.dataset, description, cases)
    version_id, examples = phoenix.examples(dataset_id)
    by_id = {c["id"]: c for c in cases}
    experiment_id = phoenix.experiment(dataset_id, version_id, args.name, args.description, {"commit": os.environ.get("GIT_COMMIT", "")})
    tally = {}
    for ex in examples:
        case = by_id.get((ex.get("metadata") or {}).get("case_id"))
        if not case or (args.only and args.only not in case["id"]):
            continue
        started = _now()
        output = run_case(case, lambda q, prev: agents.run_pipeline(q, prev=prev))
        scores = evaluate(case, output)
        if args.judges and case["expect"] == "answer":
            from tools.phoenix_judges import judge

            scores.update(judge(case["question"], output["answer"], output["citations"]))
        phoenix.record(experiment_id, ex["id"], output, started, _now(), scores)
        for name, r in scores.items():
            tally.setdefault(name, []).append(r["score"])
        print(f"{case['id']:34} " + " ".join(f"{n}={'ok' if r['score'] else 'FAIL'}" for n, r in scores.items()), flush=True)
    print("\n".join(f"{n:28} {sum(v)}/{len(v)}" for n, v in sorted(tally.items())))
    print("experiment", experiment_id, "dataset", dataset_id)


if __name__ == "__main__":
    main()
