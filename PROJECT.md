# PROJECT

**Precedent is a production legal search engine.** It answers a legal question with a short memo whose every citation comes from cases it actually retrieved, and it refuses to present a draft whose claims its own checker cannot ground.

This supersedes the hackathon framing in `docs/PLAN.md` and `docs/HACKATHON_POLICY.md`. Those remain as historical records; they no longer govern decisions.

## What it is, and is not

**Is:** a first-pass research tool for law firms and in-house teams. Fast, cited, verifiable, and explicit about jurisdiction and uncertainty.

**Is not:** legal advice, a chatbot, a case-management system, or a substitute for reading the cited cases. Every answer carries that disclaimer and will continue to.

## Where it actually stands

Measured on 2026-11-01 against the live deployment. These numbers, not the demo, define the starting point.

| Property | Measured | Verdict |
| --- | --- | --- |
| Retrieval determinism | identical top-12 on 80 of 80 questions, two runs | production-grade |
| Warm latency | 1089 ms p50, 1255 ms p95; cold start 4588 ms | acceptable, cold start is not |
| Citation support judge | MiniCheck 98.8% accuracy, 0 false alarms on 80 labelled pairs | production-grade |
| Answer grounding | **20 of 20 stored answers fail the support gate** | **blocking** |
| Citation graph contribution | 25 additions across 20 queries, **0 reached the results**; when forced in, they are citation proximity rather than relevance | **not fit for purpose** |
| Retrieval quality | **unmeasured** — no relevance judgements exist | **blocking** |

Two things are blocking and both are content problems, not plumbing: answers are not grounded, and retrieval quality cannot be stated.

## Decisions

### Use what works; do not rebuild what is already solved

| Need | Decision | Rationale |
| --- | --- | --- |
| Citation graph | **Replace with CourtListener** (Free Law Project) | 9M+ opinions, citation network already resolved, free API, Colorado covered. Our `edges.jsonl` is a one-hop approximation that admits tax cases for property questions |
| Citation parsing | **Keep eyecite** | 165 citations across 200 passages, resolves `id.`/`supra`/short forms; twice a naive regex |
| Support judging | **Keep MiniCheck** | 98.8% accuracy, zero false alarms, no per-call cost, 332 ms. Beat JEV on precision and GLiNER by 49 points |
| Retrieval engine | **Keep** (BM25 + dense + RRF + cross-encoder) | Standard stack, deterministic, 1.1 s warm. Replacing it changes nothing measurable |
| Evaluation | **Adopt LegalBench-RAG's method** | Character-level span matching gives deterministic precision/recall without a labelling project |
| Grounding | **Move upstream** — require claim→quoted-span pairs at generation | Checking ungrounded prose after the fact cannot pass; the gate must shape the draft |

### Explicitly rejected, with evidence

- **GLiNER as a judge** — 50.0% accuracy on 80 labelled pairs, i.e. chance. It accepted 30 of 50 unsupported pairs.
- **GLiNER as a ranking signal** — Spearman −0.101 against the engine order, top-10 overlap 1.9/10, 1301 ms/pair (~65 s per query). Unrelated ordering at 60× latency.
- **JEV as the primary judge** — 97.5% accuracy, but 0.023 USD per 1,000 pairs and no precision advantage over MiniCheck. Keep as a second opinion, not the gate.
- **Fixing the graph merge order alone** — tested; makes the graph visible and the visible content is mostly irrelevant. Necessary but not sufficient.
- **Wholesale migration to Vespa/Onyx/RAGFlow** — not justified while retrieval quality is unmeasured. Revisit after labels exist.

### Corpus sources assessed

- **CourtListener / Free Law Project** — the citation graph and case search to adopt.
- **JusticeDAO** (HuggingFace) — 322 datasets, **no models**. Its `ipfs_american_municipal_law_normalized_graphrag` shows the right layout (per-state BM25, pinned embeddings, per-state citation graph) but holds municipal code, not case law, and sets `authorizing_for_publication: false`. Useful as an architecture reference, not a dependency.
- **Caselaw Access Project** — bulk Colorado opinions if the Octo corpus needs widening.

## What changes from hackathon mode

| Hackathon practice | Production rule |
| --- | --- |
| Feature freeze at 15:30 ET | No freeze; every change ships behind tests and a deploy health check |
| "Demo works" as acceptance | Measured behaviour on a labelled set, recorded in `docs/experiments/` |
| Any citation check is better than none | The gate must be measured; a judge at chance is worse than no judge because it looks like it works |
| Secrets in `.hack_env` on one box | Secrets from the Octo vault, leased, with expiry recorded |
| Issue logs as notes | Issue logs as the defect record, with evidence and uncertainty, resolved against a PR |

## Not yet production-ready

These are unresolved and must not be described as done:

1. **No relevance labels.** Retrieval quality cannot be stated. Highest priority.
2. **Answers fail grounding 20/20.** The generation prompt must emit claims tied to quoted spans.
3. **No authoritative corpus licence.** The Octo snapshot's provenance and redistribution rights need confirming before commercial use.
4. **Single host.** One VPS, one process, no redundancy; cold start is 4.6 s.
5. **No usage limits, audit trail, or per-tenant isolation.**
6. **The engine source is outside version control** apart from a local baseline commit made on 2026-11-01.

## References

- `docs/RETRIEVAL_SAFEGUARD_FINDINGS.md` — what the measurements show
- `docs/experiments/` — claim-support comparison, GLiNER ranking, eyecite, 80-question regression, graph merge
- `AGENTS.md` — how work is done in this repo
