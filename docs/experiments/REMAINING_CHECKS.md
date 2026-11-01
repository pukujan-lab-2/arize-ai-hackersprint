# Three remaining checks

Items 2, 3 and 4 from the work list, each measured against the live system. Data is in the `results.json` beside each section.

## 3. GLiNER as a ranking signal

Tested anyway, after it scored at chance as a support judge.

Eight development queries, the 50 documents the engine returned for each, 387 query-document pairs, scored with the same pinned checkpoint and a 350-word cut.

| Query | n | Spearman (GLiNER, engine rank) | Top-10 overlap |
| --- | --- | --- | --- |
| dev-veh-01 | 50 | −0.293 | 2/10 |
| dev-veh-02 | 50 | 0.034 | 1/10 |
| dev-veh-03 | 50 | −0.094 | 2/10 |
| dev-veh-04 | 50 | 0.003 | 1/10 |
| dev-veh-05 | 50 | −0.131 | 2/10 |
| dev-prop-06 | 50 | −0.118 | 2/10 |
| dev-prop-07 | 37 | −0.147 | 3/10 |
| dev-prop-08 | 50 | −0.060 | 2/10 |

Mean Spearman **−0.101**, mean top-10 overlap **1.9 of 10**.

So GLiNER's ordering has essentially no relationship to the engine's: it puts almost entirely different documents in the top ten. Without relevance labels there is no way to say which ordering is *better*, but two things are already clear.

First, it is not a refinement of the engine's ranking — it is an unrelated one, and swapping to it would replace whatever the hybrid stage is doing rather than sharpen it.

Second, the cost is decisive. At 1301 ms per pair, re-scoring 50 documents takes about 65 seconds per query, against a warm engine median of 1.1 seconds for the whole retrieval. That is roughly sixty times the query latency for an ordering that agrees with the current one on two documents out of ten.

Recommendation: do not add GLiNER as a ranking signal on this evidence. The cheap version of the same experiment, if it is ever wanted, is to use its score only as a tie-breaker inside the reranked head, where it cannot reorder anything the cross-encoder already fixed.

## 2. Citation extraction: eyecite

`eyecite` installed and run over 200 real pooled passages (Colorado opinions).

| Measure | Result |
| --- | --- |
| Citations found | 165 |
| Per passage | 0.82 |
| Naive regex matches | 87 |
| Passages with no citation | 140 of 200 |

By type: 97 full case citations, 23 unknown, 17 short-form, 16 `id.`, 10 `supra`, 2 full statute citations.

eyecite finds roughly twice what a naive reporter-pattern regex finds, which is the expected result: it resolves short forms, `id.`, and `supra` against earlier citations in the same document, and those are invisible to a regex.

**The GLiNER comparison and the CAP labels are not done.** The CAP set on the deployment host is `~/precedent/data/edges.jsonl`, which is a case-to-case citation graph, not a list of inline citation strings. Comparing it to eyecite's output requires resolving each extracted citation to a case id, which is a different and larger job than counting matches. The honest state is that eyecite's extraction is measured and the comparison it was meant to feed is not.

## 4. Regression check on all 80 questions

Two captures of the full 80-question set, production settings (`graph` on, `rerank` on, `rerank_k=30`, `k=50`), back to back.

| Measure | Result |
| --- | --- |
| Queries | 80 |
| Identical top-12 | **80 of 80** |
| Identical full result list | **80 of 80** |
| Corpus revision | `octo-chunk:804646` in both |
| Graph revision | `5f469d7d` in both |
| Cold start, run A | 4588 ms |
| Warm p50 / p95, run A | 3865 / 4386 ms |
| Cold start, run B | 1301 ms |
| Warm p50 / p95, run B | 1089 / 1255 ms |

Retrieval is deterministic across runs: identical ordering on all eighty questions, so a future change that alters the top-k is a real signal rather than noise.

The two runs differ by 3.5× in warm latency, and the difference is the engine's state, not the corpus: run A was the first capture after an idle period, so the dense model and the BM25 index were cold. Run B followed it immediately. This is the same cold-versus-warm effect seen earlier on the development split, and it is why the two are reported separately.

**Caveat on "cold page cache".** The intended check was scoring speed with the OS page cache dropped. That needs root on the deployment host and was not attempted; run A is engine-cold, not OS-cold. A true cold-cache number would be lower than A's and higher than B's.
