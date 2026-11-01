# Retrieval and safeguard findings

Measured against the live engine on 2026-11-01, plus the stored answer runs on the deployment host. Labels are unreviewed throughout: these are mechanism observations, not quality scores.

## Method

Twenty development questions, four captures: graph on and off with reranking off, then graph on and off with reranking on at `rerank_k=30`. All four used `k=50`. Captures call `app/engine.py::retrieve` directly, so they bypass the application cache (`cache/octo/`, the shared `retrieval` table) and the ACS hotload watcher, neither of which can influence a result.

Both arms reported corpus `octo-chunk:804646` and graph `5f469d7d` in every run, so the comparisons are inside one revision. The pooled union across the two arms is 987 query-document pairs.

## Finding 1: the citation graph cannot change the result list

Graph on and graph off returned **identical result lists on all 20 queries** — top 12 and full 50 — with reranking off and again with it on.

The graph stage did run: 200 frontier documents and 877 edges scanned across the twenty. Five queries produced additions, 25 documents in total. None of the 25 reached the results.

The cause is in `pipeline.py`, not in the graph:

```python
final_score = {d: fused.get(d, 0.0) for d in pool}
ranked = sorted(pool, key=lambda d: (-final_score[d], d))
```

Graph neighbours are appended to `pool` but never enter `fused`, so they score `0.0` and sort below every hybrid candidate. Reranking rewrites only `ranked[:rerank_k]`, so it cannot lift them either. The response is then cut to `k`.

The hybrid stage returns 83 candidates for these queries and `k` is capped at 50. An addition therefore sits at rank 84 or lower: unreachable by construction, at any supported `k`. Production uses the same ordering with a smaller rerank window, so it is worse there, not better.

Consequence: the graph costs about 50 ms per query warm and changes nothing a user sees. A graph-versus-hybrid comparison on this corpus measures starvation, not the graph's judgement. Fixing the merge order has to come before any ranking evaluation.

## Finding 2: the safeguard fails every answer, for a structural reason

Fifteen of the last fifteen stored runs failed the safeguard. Every failure was an abstain from the support check, with confidence between 0.008 and 0.044 and clustered on two values — the signature of a structural input fault, not fifteen separate judgements.

Two causes, both in `app/agents.py`:

1. **Sentence splitting** counted a citation written after a full stop as a new sentence, so the preceding sentence looked uncited. Fixed by PR #160 (`split_sentences`), which keeps the citation group with the sentence before it.
2. **Quote collapse, still open.** `_cited_span` returns only the matched quoted substring when the sentence contains a quotation:

   ```python
   quote = _QUOTE.search(sentence)
   if quote:
       ... return p["chunk_id"], raw[at : at + len(needle)]
   ```

   A sentence quoting a phrase therefore hands the checker those few words as the entire passage. The checker is healthy: a well-formed claim and passage pair scored 0.98 in 76 ms against `lytang/MiniCheck-RoBERTa-Large`.

Consequence: end-to-end answer quality cannot be measured while every answer fails the gate, and users see "citation check failed" on answers whose citations are fine.

### The formatting fix does not explain the failures

Replaying the twenty most recent stored answers through both splitters settles the question:

| Measure | Result |
| --- | --- |
| Runs where the old splitter flagged an uncited claim | 2 of 20 |
| Runs where the new splitter flags one | 1 of 20 |
| Runs that went from flagged to clean | **0 of 20** |
| Runs still failing the gate | **20 of 20** |

One run dropped from two flagged claims to one (`073043-d0159c`); one stayed at two (`054122-b8aa5e`). No answer became clean, and every run still fails.

So PR #160 fixed a genuine formatting bug that affects a small minority of sentences, but it is **not** the cause of the failures. With uncited claims at zero in 18 of 20 runs, the citation guard passes and the gate is failing on the support check alone.

### What the support check is actually rejecting

Per-claim scoring on a stored answer, before any change:

| Claim | Score | Shape |
| --- | --- | --- |
| 0 | 0.514 | prose summary sentence |
| 1 | 0.408 | `Thiret** [1] - "the police may conduct…"` |
| 2 | 0.156 | `Barton** [2] - "Due to its mobility…" - **People v.` |
| 3 | 0.241 | `Coulson** [7] - "the opportunity…"` |
| 4 | 0.051 | `Romero** [3] - "The police could have…" ###` |

Two things are true at once. Claims 1 to 4 are bullet fragments, and across ten runs **36 of 50 claims were verbatim quotations of their own cited passage** — supported by construction, yet scored as unsupported. That is a real defect, now fixed: `support_claims` marks a claim `verbatim` when its quotation appears word for word in the cited text, and `_support` stops sending those to the model.

It does not fix the pass rate. After the change, ten runs still fail, because the one to three prose claims that remain keep scoring below the threshold (0.09 to 0.41). The aggregation is a mean, so a single weak claim pulls the answer under 0.5.

**So the gate is right about the prose and was wrong about the quotations.** These answers each contain at least one prose sentence that MiniCheck does not consider supported by the passage it cites. That is a grounding problem in answer generation, not a bug in the check, and it is not fixable from the safeguard side.

### Also changed

`_cited_span` now returns a window of the passage around the quoted phrase instead of the phrase alone, so the checker reads prose rather than six words. Measured on ten runs this made no difference to the pass rate (0 of 10 either way) and moved the scores slightly down, which is worth recording because the opposite was expected.

## Finding 3: attribution comes from the graph stage, not from provenance

Real result rows carry `provenance` naming only `bm25` and `dense`. Inferring graph-only candidates from provenance therefore yields nothing at all. The graph stage does report `frontier`, `edges_scanned`, `hops`, `edges` and `added[]` with `doc_id`, so graph-only means membership in `added` and absence of a hybrid source.

An addition that never reaches the results is a finding, not a defective capture, and is reported as `graph_added_not_returned` rather than failing the query.

## Finding 4: latency, split correctly

Warm, graph on was 613 ms p50 / 768 p95 against 563 / 702 with it off, so expansion costs about 50 ms. With reranking on the pair became 1044 / 1228 and 995 / 1161, so reranking costs about 430 ms.

A first capture measured 3.4 s p50 for the graph arm. That was entirely cold dense-model load, not graph cost, and it is why cold start is reported separately from warm percentiles.

## Access reality

- **GLiNER.** Not installed on the engine host or the app host. The Windows host has `torch 2.13.0` and every `gliner2` dependency already satisfied, so `pip install gliner2` there is a small wheel and no torch download. That is the cheapest place to run it.
- **JEV.** `src/legal_graph/jev.py` posts to `https://openrouter.ai/api/alpha/decisions` with model `typesafe/jev-1.14` and needs `OPENROUTER_API_KEY`. Without it the engine skips the stage with `OPENROUTER_API_KEY not configured`.
- **MiniCheck.** Installed and cached on the engine host, reachable through `engine.check`.
- **eyecite.** Not installed anywhere yet.
- **Engine source is not version controlled.** `~/apps/legal-engine` on the deployment host has no git directory, so a `pipeline.py` change has no review path.

## Open work

| Item | Status | Notes |
| --- | --- | --- |
| Claim-support: GLiNER vs MiniCheck vs JEV | Not started | Needs labelled pairs; blocked by Finding 2 on the pair-construction side |
| Citation extraction: eyecite vs GLiNER | Not started | Needs eyecite installed and the CAP citation set located |
| Retrieval ranking, 80 questions, GLiNER signal | Infrastructure only | Harness merged; blocked by Finding 1 |
| PR 50 regression: cold cache, identical top-k, end to end | Not started | Mechanical |
| Safeguard regression: old vs new splitting | Not started | Now measurable; PR #160 supplies the new splitter |

### How to build the claim-support pair set

Labels must be knowable rather than judged, or the comparison measures the labeller:

- **Supported**: a sentence taken from a passage, paired with its own passage.
- **Unsupported**: the same sentence paired with an unrelated passage.
- **Hard negatives**: the sentence with a citation number or a quantity altered, paired with the original passage.

Passages must be cut to the model's 512-token limit, and the same cut applied to every scorer, or the comparison is measuring context windows.
