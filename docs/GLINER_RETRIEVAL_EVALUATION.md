# Evaluate GLiNER retrieval on a reviewed query set

A search for “reasonable use” can return a road easement even when the question asks about water rights. This proposed set gives us 80 questions for checking whether retrieval finds the requested legal issue. The questions are unreviewed. They do not name a case as relevant or assert what any court held.

## Query set

The fixture `tests/fixtures/retrieval_eval_questions.json` contains 20 development questions and 60 held-out test questions. Each of the four topics has five development and fifteen test questions: vehicle search, property, water rights, and other legal topics. IDs and group IDs are unique; no paraphrase group crosses the split. The set includes hard negatives, questions expected to have no answer in the corpus, and underspecified questions. Those expectations are proposed labels for review, not established corpus facts.

Tune prompts, thresholds, and ranking choices with development questions only. Keep the test split sealed until the setup is fixed. Do not add qrels by guessing which cases ought to match. Before scoring, pool the returned documents, hide the system name and rank, and have a qualified legal-domain reviewer grade each query-document pair: 0 means irrelevant, 1 means useful context, and 2 means directly useful to the question. Record current authority as a separate field. A second reviewer should resolve disagreements where feasible. Freeze and version the reviewed qrels before comparing systems. If an agent or model proposes labels, report them as provisional until a qualified reviewer checks them.

## Two experiments

### 1. Compare candidate ranking

Freeze one candidate pool per query before reranking. Compare the MiniLM baseline, the English GLiNER boundary/multi setup, and rank fusion on that same pool, with equal candidate and compute budgets. Log candidate IDs and ranks at every stage. GLiNER scores are uncalibrated; do not use them to drop candidates. Any filtering variant needs its own labeled development study and must preserve the unfiltered pool for comparison.

This stage asks whether GLiNER signals improve candidate ordering. It does not measure graph retrieval.

### 2. Compare retrieval sources

Compare hybrid retrieval, graph retrieval, and GLiNER-guided graph retrieval only when the run exposes actual graph adjacency and permits the same query, corpus snapshot, and candidate budget across arms. Record the graph frontier, edges scanned, capped edges, added document IDs and their source node, and candidate survival after fusion and reranking. Report graph-only relevant candidates and whether they reach the final ranked list.

The current engine matters to interpretation: dense scoring runs over the BM25 candidate pool, not an independent corpus-wide ANN search. Graph-only neighbors receive RRF score 0 and append after hybrid candidates; the default reranker sees only the first 30. A graph candidate can therefore be added and then starved before reranking. Compare actual graph and hybrid arms to isolate that effect. A change in the final top 12 alone cannot establish graph improvement.

## Model pins and where the model runs

The reranker can run in two places, and the run records which one scored it.

**Served elsewhere.** Point `--endpoint` at the host serving GLiNER2, for example `--endpoint http://<host>:8080`, with `FASTINO_API_KEY` or `GLINER2_API_KEY` in the environment. `--endpoint` falls back to `GLINER2_API_BASE_URL`. The client posts to `{endpoint}/gliner-2` with an `X-API-Key` header. It uses the `gliner2` SDK when that imports, and otherwise calls the same documented contract directly, because importing `gliner2` pulls torch even for a client call. The run records `client: sdk` or `client: http`.

**Local.** `--local` loads the pinned checkpoint on the machine doing the scoring, which needs torch installed separately.

A served endpoint takes its model from the server. The API payload carries no model or revision field, so the pin cannot be enforced or checked over the wire. A remote run therefore records `model_pin_enforced: false` and leaves `model` and `revision` null instead of claiming weights it never verified. If a comparison turns on a specific checkpoint, either run it locally or confirm out of band what the server is serving and write that into the run notes.

The pins themselves, resolved against the Hub on 2026-11-01: `GLiNER2.5-Decide` at `9d1bfb848cd16d93ee56ccbc59cd92bf0f284d90`, `GLiNER2.5-multi-Decide` at `9f18c1a7c2d0ba24bd89756bda06af2bf77e2649`. Both resolve as historical commits. `GLiNER2.5-multi-Decide` has since moved to `e173bca1`; that newer commit is not adopted here, because changing the model mid-experiment needs a new dataset version rather than a quiet upgrade. An eight-character SHA prefix is not an acceptable pin.

Whatever the mode, `threshold=0.0` is deliberate: this is a ranking signal, so a passage scoring 0.51 has to outrank one scoring 0.50 instead of both falling below a cut-off. A passage the model leaves unlabelled scores 0.

## Access and evidence limits

The public `/api/ask` route returns an answer and does not expose the authenticated retrieval controls needed for a controlled comparison. The authenticated engine route `/api/v1/retrieve` supports graph true/false and exposes retrieval-stage output. Use that route for candidate comparisons and record the response, request settings, and access path. Do not treat a public answer as a candidate list.

Production currently defaults to graph enabled, `graph_seed_docs=10`, reranking enabled, and `rerank_k=30`. The engine accepts a maximum `k` of 50 and `rerank_k` of 100. A request for `k=100` does not capture a complete corpus candidate pool. Report the actual pool and caps. The `GET run.edges` view is a separate local graph among selected authorities; it does not show that the retrieval engine skipped graph expansion.

The three queries in `/tmp/precedent-graph-comparison-input.json` were exploratory. They have no reviewed relevance labels and must not enter the test split or count as evaluation results.

`capture` calls `app/engine.py::retrieve` directly, so it never touches the application's retrieval cache — neither `cache/octo/` nor the shared `retrieval` table in the Octo workspace. Capturing through the app route or through `octo_retriever.search()` would return cached passages and report warm-cache behaviour as retrieval behaviour. Keep the capture on the engine client. The same isolation means the ACS hotload watcher plays no part in a capture: it is mounted in `app/server.py` and watches coordination files (`assignment.json`, `board.json`, `hotload.lock.json`, `acs/config.json`), none of which affect retrieval, and the harness process never imports it.

## Verified response contract

`tools/retrieval_eval.py` reads the engine through `app/engine.py::retrieve` and maps each row the way `app/octo_retriever.py::_from_engine` already does. A row is one entry of `result.results`: `case` (`id`, `name`, `court`, `year`, `link`, `cap_id`), `passages[]` (`chunk_id`, `text`, `ord`, `bm25`, `spans`), plus `score`, `rank`, `score_kind`, `rrf`, `bm25`, `dense`, and `provenance[]`. Stage records arrive under a `stage` key, not `name`, and the graph stage carries its own detail. The details below decide whether a capture can be scored at all.

**Authority key.** The engine sometimes keys a case by an opaque row id. The app then shows the case name, and the harness applies the same rule, so pool ids match the names a reviewer grades. An opaque id in the pool would also differ between corpus snapshots, which would stop the same authority from deduplicating across arms.

**Graph attribution.** The engine does report the graph stage in detail: `frontier`, `edges_scanned`, `hops`, `edges`, and `added[]` with `doc_id`. Graph-only candidates are therefore the entries in `added` that also appear in the results, and a candidate that appears in both `added` and a hybrid source is not graph-only. `provenance` cannot carry this: on real rows it only ever names `bm25` and `dense`, so inferring graph-only from provenance yields nothing. A row with no `provenance` at all still fails the attribution gate rather than being counted as a hybrid hit.

**Starved additions.** An addition the graph reports but that never reaches the results is a finding, not a defective capture. It is counted in `graph_added_count` and listed in `graph_added_not_returned`, and it does not block scoring. Failing the capture here would block exactly the comparison the experiment exists to make.

**Pool truncation.** `bm25_k` and `dense_pool` are deeper than the `k` the engine returns, so the visible pool is always a truncation. It is reported as `pool_truncated_by_k` and must be disclosed with the actual caps; it is not the same failure as losing graph attribution, and the two are reported separately.

**Corpus provenance.** The searchable corpus is the Octo workspace's `legal_graph` tables — `chunk`, `expression`, `work` — materialised into an index the engine serves directly rather than querying Octo on each request. Its revision comes back as `octo-chunk:<chunk count>`, which is why a capture is reproducible only inside one revision. `capture` records `corpus_revisions` and `graph_revisions`, and `pool` refuses captures spanning more than one of either: a corpus that moved between arms is not a ranking difference, and averaging across it would hide that.

### What the development split showed

Twenty development queries were captured against the live engine on 2026-11-01, graph on and graph off, at `k=50` with reranking disabled. Both arms reported corpus `octo-chunk:804646` and graph `5f469d7d`, and both captured cleanly.

- The graph stage ran on every query: 200 frontier documents and 877 edges scanned across the twenty.
- Five queries produced graph additions, 25 documents in total. **None of the 25 reached the result list.** With `k=50` and reranking off, graph-only candidates were added and then starved, which is the effect the second experiment exists to isolate. It also means a graph-versus-hybrid comparison on this split would measure the starvation, not the graph's judgement.
- Warm latency was 613 ms p50 / 768 ms p95 with the graph on, and 563 ms / 702 ms with it off, so graph expansion cost about 50 ms per query once the engine was warm. A first capture measured 3.4 s p50 for the graph arm purely because the dense model was cold; that number was cold-start, not graph cost, and it is why the two are reported apart.
- Repeating both arms with reranking on at `rerank_k=30` changed nothing: the two arms returned **identical result lists on all 20 queries**, top 12 and full 50, again with 25 additions and none returned. Latency was 1044 ms p50 with the graph and 995 ms without, so reranking costs roughly 430 ms and the graph still about 50 ms.

**Why the additions never appear.** In `pipeline.py`, graph neighbours are appended to `pool` but never enter `fused`, so `final_score` gives them `0.0` and `sorted(pool, key=-score)` places every one of them below every hybrid candidate. Reranking only rewrites `ranked[:rerank_k]`, so a graph addition cannot be lifted by the reranker either. The response is then cut to `k`. With the hybrid stage already returning 83 candidates for these queries and `k` capped at 50, a graph addition sits at rank 84 or lower and is unreachable by construction. This is a property of the merge order, not of the graph's judgement, and it holds in production because production uses the same ordering with a smaller rerank window.

These are development-split observations with unreviewed labels. They are not evaluation results and must not be quoted as a system comparison.

## Scoring and timing

Report nDCG@10, precision@3, precision@10, and recall of known relevant documents. The pooled judgments can be incomplete, so call the last measure recall of known relevant documents, not corpus recall. For graph experiments, also report graph-only relevant candidate contribution and the number that survive each stage. Score no-answer and underspecified queries separately; a retrieved document is not automatically a correct answer to either.

Measure p50 and p95 latency on the same serving hardware. Report model loading/cold-start time separately from warm request time. Keep batch size, candidate budget, reranker limit, and compute budget equal across arms, or disclose each difference. Use paired query-level uncertainty intervals for metric differences. With 60 held-out questions and four topic groups, wide intervals are plausible; call the result inconclusive when the data cannot separate the systems.

The harness reports the four measures overall and again per topic and per answerability label, so a group average cannot be mistaken for the overall result. `capture` records client wall time for every query and reports the first call separately as cold start, with warm p50 and p95 after it. `compare` reports a paired bootstrap interval for each metric difference, pairing only the queries both arms score under the same pool, and states that the result is inconclusive when every interval covers zero.

`score` also reports graph-only contribution per query and in total: how many candidates the graph alone added, how many of those are relevant, and how many reached the top 3 and top 10. It is withheld with the metrics when a query is not fully judged. Stage survival cannot be reported, because the engine exposes no per-stage candidate lists.

## Command order

`tools/retrieval_eval.py` runs offline after the capture, so no scoring step touches the live engine.

```
questions  --questions Q                       # validate splits before an immutable capture
capture    --questions Q --output A --graph on # one immutable artifact per arm
pool       --captures A B --pool P --mapping M --runs R
gliner     --pool P --endpoint URL --split development --output G
fuse       --runs R --output F
review     --pool P --output S.csv             # blinded sheet for a reviewer
qrels      --review S.csv --pool P --version v1 --output J
score      --run R --run-id <arm> --pool P --qrels J --split development --output X
compare    --runs R --pool P --qrels J --output C
```

`pool` writes `R` as the per-arm rankings, and `score` and `compare` both read that file: `score` needs `--run-id` when it holds more than one arm, and `compare` takes exactly two. Both re-score against the same pool and qrels, so a comparison pairs the same queries rather than two different subsets.

`score --for-selection` refuses any split but `development`. `qrels` refuses an ungraded row unless `--allow-partial` is passed, and `score` withholds metrics for any query whose pooled candidates are not all judged, so a partial sheet produces no numbers rather than optimistic ones.

## Run checklist

1. Freeze the corpus snapshot and record its document count, exclusions, and hash or immutable version. Record API route and parameters, code revision, model names and revisions, GLiNER labels/boundaries, reranker, graph settings, candidate caps, and hardware.
2. Validate the fixture has 20 development and 60 test questions, with five and fifteen questions per topic respectively. Keep query IDs and split assignments stable. Keep exploratory queries out of the fixture.
3. Run development queries to set the candidate budget, prompts, and ranking rules. Log the full candidate list at each stage, including graph-only additions and items lost to caps.
4. Freeze the configuration and reviewed qrels. Then run the held-out queries once for the primary comparison. Do not retune against test labels; if a revision is needed, make a new dataset version and new held-out set.
5. Pool candidates across systems before blinded review. Store reviewer grades, authority judgments, reviewer identity/role, adjudications, and qrels version separately from system outputs. `review` writes the blinded sheet — no rank, no score, no system name, passages shuffled per query — and `qrels` reads it back, refusing a grade outside 0/1/2, a duplicate, an id that is not in the pool, or an ungraded row unless `--allow-partial` is passed on purpose.
6. Publish per-topic and overall metrics, paired uncertainty, latency, pool coverage, stage survival, and failures. Mark agent-generated or unreviewed labels as provisional.

## Stop gates

Do not report a system win if the corpus snapshot or candidate pool is not reproducible, the arms have unequal budgets without disclosure, graph adjacency is unavailable for the graph claim, or the test split informed tuning. `pool` enforces the first of these: captures that span two corpus or graph revisions are refused rather than merged. Stop and repair the run if candidate-stage logs cannot distinguish hybrid hits from graph-only additions. Do not present unreviewed labels as ground truth or legal conclusions. If judgments are sparse or intervals remain wide, report the comparison as inconclusive and gather more reviewed questions before making a deployment decision.

This is a retrieval evaluation, not legal advice or a measure of whether a case remains good law. Authority is reviewed and reported separately from topical relevance.
