# Building past Colorado: data, jurisdiction and a survey of what exists

Two questions: where the data comes from when the scope is no longer one state, and which of the many existing components to use instead of building. The second list is deliberately long; the verdicts are what matter.

## Part 1 — Where the data comes from

### The three sources worth using

**CourtListener / Free Law Project** is the primary. Its bulk data is a PostgreSQL `COPY TO` dump of its own tables, regenerated **quarterly** (last day of March, June, September, December), published to S3 under the **Public Domain Mark** — "free of known copyright restrictions", which is the licensing answer that matters for a commercial product.

```
https://com-courtlistener-storage.s3-us-west-2.amazonaws.com/list.html?prefix=bulk-data%2F
```

Tables, in import order: **courts** → **dockets** → **opinion clusters** → **opinions** → **citations map** → parentheticals, plus judges and oral arguments. The citations map is a narrow table of `(citing_opinion_id, cited_opinion_id, depth)` — the graph we tried to build by hand, already resolved across 9M+ opinions and 2,000+ courts.

Two things in that dump matter more than the text:

- **`courts.appeals_to`** encodes the court hierarchy. That is what turns "this case is cited" into "this case is *binding*" — the distinction a generic RAG cannot make and the main legal differentiator available for free.
- **Quarterly snapshots, not deltas.** Plan ingestion around a quarterly cut, not a live feed. The REST API (`/api/rest/v4/`) covers the gaps between cuts and offers a `citation-lookup` endpoint that resolves a citation string to a case.

There is also a **CourtListener MCP server** (public, and shipping inside Gemini Enterprise for Legal) and **case-law embeddings** — about 2TB from their fine-tuned ModernBERT (`modernbert-embed-base_finetune_512`) at `s3://com-courtlistener-storage/embeddings/opinions/`. Downloading those costs Free Law Project roughly $200 in AWS egress, so budget a donation if you take them.

**GovInfo (GPO)** is the statutes and regulations side. US Government works, public domain, with both an API (`api.data.gov` key) and a bulk repository exposing XML and JSON per collection:

```
https://www.govinfo.gov/bulkdata          bulk, /xml or /json suffixes
https://api.govinfo.gov/docs              REST API
https://github.com/usgpo/api/tree/main/docs/mcp.md   MCP server (public preview)
```

Collections: **US Code**, **eCFR** (current) and **CFR annual editions 1996–**, **Federal Register 2000–**, **Statutes at Large 1789–**, Statutes Compilations, bill text/status/summaries from the 108th–113th Congress, Public Papers, Privacy Act Issuances. Statutes arrive as **USLM** XML (`github.com/usgpo/uslm`), a real schema with sections and subsections — parse it, don't regex it.

**Caselaw Access Project** has been restructured: `case.law/bulk/` now 404s and the site advertises "long-term, unrestricted access" without a bulk index. Practically, CAP is reachable *through* CourtListener — the clusters carry `filepath_pdf_harvard` — and through Harvard LIL's `cold-cases` dataset on HuggingFace. Treat CAP as a supplement, not a pipeline.

### What to avoid

**JusticeDAO** (HuggingFace): 322 datasets, **no models**. Its `ipfs_american_municipal_law_normalized_graphrag` is a genuinely good *layout* — per-state BM25 postings, pinned `gte-small` embeddings, per-state `nodes.parquet`/`edges.parquet` — over 7.8M municipal sections. But it is municipal code rather than case law, and it states `authorizing_for_publication: false`. Copy the architecture, not the data.

### Scope, concretely

| Layer | Source | Coverage | Licence |
| --- | --- | --- | --- |
| Federal appellate + district opinions | CourtListener bulk | strong, 2000+ courts | Public Domain |
| State appellate + supreme opinions | CourtListener bulk | strong, varies by state | Public Domain |
| State trial / county courts | CourtListener, patchy | **weak — the real gap** | Public Domain |
| Federal statutes | GovInfo USCODE | complete | US Gov work |
| Federal regulations | GovInfo eCFR + CFR annual | 1996– | US Gov work |
| Federal Register | GovInfo | 2000– | US Gov work |
| State statutes | Open States + per-state sites | varies | mixed |
| Municipal / county code | Municode, American Legal, eCode360 | scrape or licence | **restricted** |

The honest shape of the expansion: **federal and state appellate case law is a solved ingestion problem; county-level and municipal law is not.** Every municipality publishes differently and several assert copyright in their annotations. If "county" means trial-court opinions, CourtListener's coverage is thin and there is no free authoritative alternative.

### How the expansion should be structured

Do not build one index with a `state` column. Build **per-jurisdiction shards** with a shared schema:

1. **Court registry** — from `courts`, with `appeals_to` and jurisdiction, giving the binding graph.
2. **Opinion shards per state**, plus a federal shard, each independently rebuildable.
3. **One citation graph**, keyed by opinion id, not per shard — citations cross jurisdictions and that is the point.
4. **Authority weighting at query time** — a case from the user's jurisdiction and a court above it outranks a persuasive citation from elsewhere, all else equal.

Step 4 is the part that makes this a legal search engine rather than a document search engine, and it is free once `appeals_to` is loaded.

## Part 2 — Survey of what exists

Verdict key: **use** (adopt), **try** (worth a spike), **skip** (measured or judged unsuitable), **gap** (nothing good exists).

### Case law corpora

1. CourtListener bulk S3 — quarterly CSV, public domain — **use**
2. CourtListener REST API v4 — search, opinions, citation lookup — **use**
3. CourtListener citations map — resolved citing/cited/depth — **use as the graph**
4. CourtListener case-law embeddings (ModernBERT, 2TB) — **try** for cold start
5. CourtListener MCP server — LLM-facing retrieval — **try**
6. Caselaw Access Project — restructured, no bulk index — supplement only
7. `harvard-lil/cold-cases` (HF) — CAP-derived — **try**
8. RECAP — federal dockets and PDFs — **skip** (dockets, not opinions)
9. GovInfo USCOURTS — opinions for some courts — **try** for gaps
10. State official reporters (Colorado, Nebraska, NC publish directly) — **gap** per state
11. JusticeDAO — 322 datasets, municipal + international — **skip** (licence)
12. vLex / Fastcase / LexisNexis — commercial — **skip** on cost

### Statutes, regulations, legislation

13. GovInfo USCODE bulk XML — **use**
14. GovInfo eCFR current XML — **use**
15. GovInfo CFR annual editions 1996– — **use** for point-in-time
16. GovInfo Federal Register 2000– — **try**
17. GovInfo Statutes at Large 1789– — **try**
18. GovInfo Statutes Compilations — **skip** initially
19. eCFR API — versioned diffs — **use** for "law at the time"
20. USLM XML schema — parse statutes structurally — **use**
21. Open States — 50-state legislation — **try**
22. Per-state code sites (CA leginfo, NY Senate API) — **gap**, one adapter each

### Municipal and county

23. JusticeDAO normalized municipal GraphRAG — layout reference only
24. Municode — scrape or licence — **gap**
25. American Legal Publishing — scrape — **gap**
26. eCode360 — scrape — **gap**
27. County codes via state municipal associations — **gap**

### Citation extraction and resolution

28. **eyecite** — already in, 2× a naive regex — **use**
29. citeurl — citation recognition, different rule set — **try**
30. CourtListener `citation-lookup` — resolve string → case — **use**
31. `reporters-db` — reporter abbreviations and volumes — **use**
32. Bluebook parsing rules — **gap** (eyecite approximates)
33. Neutral citations — court-assigned, growing — **try**
34. `id.` / `supra` resolution — eyecite does it — **use**
35. CAP citation extraction — superseded by CourtListener — **skip**

### Ingestion and parsing

36. docling (IBM) — PDF/HTML → structured — **try**
37. unstructured — broad format support — **try**
38. marker — PDF → markdown, fast — **try**
39. PyMuPDF — low-level, reliable — **use** as fallback
40. pdfplumber — tables — **skip**
41. trafilatura — HTML main-text — **use** for scraped pages
42. jusText — boilerplate removal — **skip** (trafilatura better)
43. Apache Tika — format sprawl — **skip** (JVM for little gain)
44. GROBID — scholarly structure — **skip** (wrong domain)
45. OCR: Tesseract / PaddleOCR / Surya — **try** Surya, old scans only

### Chunking

46. Fixed token windows — current behaviour — **skip**
47. Sentence-aware splitting — **use** (already)
48. Section/paragraph-aware for statutes via USLM — **use**
49. Semantic chunking at embedding breakpoints — **try**
50. Hierarchical chunking (case → opinion → section → para) — **use**
51. Late chunking (Jina) — **try**
52. Contextual retrieval (Anthropic: prepend doc context per chunk) — **try**, cheap and reported to help

### Lexical retrieval

53. BM25 in Elasticsearch/OpenSearch — **use**
54. BM25F field-weighted (title, headnote, body) — **use**
55. SPLADE — learned sparse, stronger recall — **try**
56. uniCOIL / DeepImpact — **skip** (SPLADE supersedes)
57. BGE-M3 sparse head — **try** (one model, three modes)
58. Tantivy — Rust BM25, embedded — **try** if dropping ES
59. Postgres `tsvector` — **skip** at this scale
60. SQLite FTS5 — **skip** except for tests

### Dense retrieval

61. BGE-M3 — multilingual, dense+sparse+multi-vector — **use**
62. multilingual-e5 — solid baseline — **try**
63. GTE (thenlper) — small, fast, already in JusticeDAO layout — **try**
64. ModernBERT-embed (CourtListener's fine-tune) — legal-tuned — **use**
65. NV-Embed / E5-Mistral — LLM embedders, strong but heavy — **try**
66. Jina v3 — long context — **try**
67. Cohere embed — commercial — **skip**
68. OpenAI text-embedding-3 — commercial, no legal tuning — **skip**
69. voyage-law-2 — legal-specific embeddings, commercial — **try** if budget
70. Legal-BERT / CaseLaw-BERT — small and dated — **skip**
71. ColBERTv2 — late interaction — **try**
72. PLAID — ColBERT index — **try** with 71

### Fusion

73. RRF — current — **use**
74. Weighted RRF — **use**, tune per field
75. Convex combination of normalised scores — **try**
76. Learning-to-rank fusion — **try** once labels exist
77. CombSUM / CombMNZ — **skip**
78. RRF with tuned k (60 default, 10–100 range) — **use**, cheap win

### Reranking

79. bge-reranker-v2-m3 — **use**
80. ms-marco-MiniLM cross-encoder — current — **use**
81. Cohere rerank — commercial — **skip**
82. Jina reranker — **try**
83. `rerankers` (answer.ai) — one API over many — **use** for swapping
84. ColBERT rerank — **try**
85. LLM listwise rerank — expensive, strong — **try** on head only
86. MonoT5 — **skip**
87. RankGPT — **try** (same family as 85)
88. Setwise reranking — **skip**

### Graph retrieval

89. CourtListener citations map — **use**
90. PageRank over the citation graph — current, weak — **use** but see 96
91. Personalized PageRank from seeds — **use**
92. HippoRAG — PPR-based retrieval — **try**
93. Microsoft GraphRAG — entity graph + community summaries — **skip** (expensive, entity graph not legal)
94. LightRAG — lighter GraphRAG — **try**
95. Neo4j GDS — graph algorithms as a service — **try**
96. Authority by court level × in-degree — **use**; this is what PageRank is missing

### Query understanding

97. Follow-up rewriting — already in — **use**
98. HyDE — hypothetical answer then embed — **try**
99. Query decomposition into sub-issues — **try**
100. Jurisdiction detection from the question — **use**
101. Citation-anchored queries ("cases citing X") — **use**
102. Fielded/boolean query support for professional users — **use**

### Generation and grounding

103. Claim → quoted-span constrained generation — **use**, the fix
104. Quote-first prompting (answer only from spans) — **use**
105. ALCE-style citation evaluation — **use**
106. **MiniCheck** — measured 98.8% here — **use**
107. JEV — 97.5%, paid — second opinion only
108. AlignScore — **try**
109. NLI entailment (DeBERTa-MNLI) — **skip** (MiniCheck better)
110. RAGAS faithfulness — **try** for reporting
111. TruLens groundedness — **try**
112. Self-RAG / CRAG patterns — **skip** (adds latency, unproven here)

### Evaluation

113. **LegalBench-RAG** — character-level precision/recall, 6,858 spans — **use**
114. BEIR / MTEB — general IR/embedding benchmarks — **use** for model choice
115. Our own nDCG harness — **use** for internal comparisons
116. ir_measures — IR metrics library — **use**
117. ranx — alternative — **skip** (pick one)
118. trec_eval — the standard — **skip** (ir_measures wraps it)
119. promptfoo — LLM eval and regression — **try**
120. DeepEval — pytest-style LLM tests — **try**
121. Arize Phoenix / Langfuse — tracing + evals — **use** (tracing already present)

### Serving and infrastructure

122. Vespa — hybrid + ranking + serving in one — **try** if replacing the engine
123. Elasticsearch / OpenSearch — BM25 + kNN + RRF — **use**
124. Qdrant — vector, hybrid — **try**
125. Weaviate — hybrid built in — **try**
126. Milvus — scale — **skip** (overkill now)
127. pgvector — one database — **try** if consolidating
128. LanceDB — embedded, columnar — **skip**
129. Redis vector — cache + vectors — **try**
130. FastAPI + uvicorn — current — **use**
131. Ray Serve / Modal — GPU autoscaling — **try** for rerank fleet

### Legal-specific ranking signals

132. Court hierarchy (`appeals_to`) — binding vs persuasive — **use**, highest value
133. Jurisdiction match to the user — **use**
134. Recency within a court — **use**
135. Treatment signals (followed / distinguished / overruled) — **gap**
136. Citator (KeyCite / Shepard's equivalent) — **gap**; CourtListener has no citator, and a production legal product without one is selling something it cannot back
137. Judge and court authority metadata — **use** (in bulk data)

### What the survey changes

Three conclusions, in order of value:

1. **The citation graph is a solved problem** and we were rebuilding it badly. CourtListener ships the resolved edges plus the court hierarchy, under a public-domain licence, quarterly.
2. **The expansion is an ingestion problem for appellate law and an unsolved problem for county law.** Federal and state appellate: load the bulk dump and shard by state. County and municipal: no free authoritative source, and several assert rights over annotations.
3. **The differentiator is not the retriever.** Every item in sections 6–10 is commodity. Binding-authority weighting (132–134) is free once the court table is loaded, and a citator (136) is the one thing a production legal product needs that no free source provides. That gap is the real product decision.
