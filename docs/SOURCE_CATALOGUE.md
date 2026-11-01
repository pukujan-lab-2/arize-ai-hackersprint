# Source catalogue

154 sources, each link requested once on 2026-11-01 and kept only if it resolved. Two entries
(CanLII, AustLII) return 403 to scripted requests but are live sites; they are marked. Nothing here is
listed from memory without a check.

Companion to `LEGAL_DATA_AND_STACK_SURVEY.md`, which carries the verdicts. This file is the evidence:
where each thing actually is.

## Corpora (8)

| # | Source | What it is |
| --- | --- | --- |
| 1 | [www.courtlistener.com/](https://www.courtlistener.com/) | Free Law Project's case-law search; 9M+ opinions, 2000+ courts |
| 2 | [www.courtlistener.com/api/rest/v4/](https://www.courtlistener.com/api/rest/v4/) | REST API v4: search, opinions, citation-lookup |
| 3 | [com-courtlistener-storage.s3-us-west-2.amazonaws.com/list.html](https://com-courtlistener-storage.s3-us-west-2.amazonaws.com/list.html?prefix=bulk-data%2F) | Bulk S3 index: quarterly PostgreSQL dumps, Public Domain |
| 4 | [wiki.free.law/c/courtlistener/help/api/bulk-data/bulk-legal-da](https://wiki.free.law/c/courtlistener/help/api/bulk-data/bulk-legal-data) | Bulk data docs: tables, import order, citations map |
| 5 | [www.courtlistener.com/recap/](https://www.courtlistener.com/recap/) | RECAP: federal dockets and PACER documents |
| 6 | [case.law/](https://case.law/) | Caselaw Access Project; bulk index retired, reachable via CourtListener |
| 7 | [huggingface.co/datasets/harvard-lil/cold-cases](https://huggingface.co/datasets/harvard-lil/cold-cases) | Harvard LIL cold-cases dataset, CAP-derived |
| 8 | [huggingface.co/justicedao](https://huggingface.co/justicedao) | 322 legal datasets, no models; municipal + international |

## Statutes (12)

| # | Source | What it is |
| --- | --- | --- |
| 9 | [www.govinfo.gov/bulkdata](https://www.govinfo.gov/bulkdata) | GPO bulk XML/JSON: US Code, CFR, Federal Register, Statutes at Large |
| 10 | [api.govinfo.gov/docs](https://api.govinfo.gov/docs) | GovInfo REST API (api.data.gov key) |
| 11 | [github.com/usgpo/uslm](https://github.com/usgpo/uslm) | USLM schema: structured statutes, not plain text |
| 12 | [github.com/usgpo/api](https://github.com/usgpo/api) | GovInfo API source, incl. MCP server docs |
| 13 | [www.ecfr.gov/](https://www.ecfr.gov/) | eCFR: current CFR with point-in-time versions |
| 14 | [openstates.org/](https://openstates.org/) | 50-state legislation API |
| 15 | [github.com/openstates/openstates](https://github.com/openstates/openstates) | Open States scrapers and data pipeline |
| 16 | [www.federalregister.gov/developers/documentation/api/v1](https://www.federalregister.gov/developers/documentation/api/v1) | Federal Register API v1 |
| 17 | [eur-lex.europa.eu/](https://eur-lex.europa.eu/) | EU law portal (multilingual, for non-US expansion) |
| 18 | [www.legislation.gov.uk/](https://www.legislation.gov.uk/) | UK legislation, structured XML |
| 19 | [www.canlii.org/](https://www.canlii.org/) *(403 to scripts)* | Canadian legal database (bot-blocked to curl; real) |
| 20 | [www.austlii.edu.au/](https://www.austlii.edu.au/) *(403 to scripts)* | Australasian legal information (bot-blocked to curl; real) |

## Citations (7)

| # | Source | What it is |
| --- | --- | --- |
| 21 | [github.com/freelawproject/eyecite](https://github.com/freelawproject/eyecite) | Citation parser: resolves id./supra/short forms |
| 22 | [github.com/freelawproject/reporters-db](https://github.com/freelawproject/reporters-db) | Reporter abbreviations and volumes |
| 23 | [github.com/freelawproject/courts-db](https://github.com/freelawproject/courts-db) | Court identifiers and hierarchy |
| 24 | [github.com/freelawproject/juriscraper](https://github.com/freelawproject/juriscraper) | Scraper framework for American court sites |
| 25 | [github.com/freelawproject/courtlistener](https://github.com/freelawproject/courtlistener) | CourtListener source: schema, citation logic |
| 26 | [free.law/open-source-tools/](https://free.law/open-source-tools/) | Index of Free Law Project's open-source tools |
| 27 | [github.com/LexPredict/lexpredict-lexnlp](https://github.com/LexPredict/lexpredict-lexnlp) | Legal text NLP: dates, amounts, definitions, citations |

## Legal NLP (2)

| # | Source | What it is |
| --- | --- | --- |
| 28 | [huggingface.co/nlpaueb/legal-bert-base-uncased](https://huggingface.co/nlpaueb/legal-bert-base-uncased) | Legal-BERT weights; small and dated, baseline only |
| 29 | [huggingface.co/datasets/pile-of-law/pile-of-law](https://huggingface.co/datasets/pile-of-law/pile-of-law) | Pile-of-Law: large legal pretraining corpus |

## Benchmarks (10)

| # | Source | What it is |
| --- | --- | --- |
| 30 | [hazyresearch.stanford.edu/legalbench/](https://hazyresearch.stanford.edu/legalbench/) | LegalBench: 162 legal reasoning tasks |
| 31 | [github.com/HazyResearch/legalbench](https://github.com/HazyResearch/legalbench) | LegalBench source |
| 32 | [github.com/zeroentropy-ai/legalbenchrag](https://github.com/zeroentropy-ai/legalbenchrag) | LegalBench-RAG: character-level precision/recall, 6,858 spans |
| 33 | [github.com/coastalcph/lex-glue](https://github.com/coastalcph/lex-glue) | LexGLUE: legal language understanding suite |
| 34 | [huggingface.co/datasets/coastalcph/lex_glue](https://huggingface.co/datasets/coastalcph/lex_glue) | LexGLUE datasets on the Hub |
| 35 | [github.com/reglab/casehold](https://github.com/reglab/casehold) | CaseHOLD: holding identification from case text |
| 36 | [github.com/princeton-nlp/ALCE](https://github.com/princeton-nlp/ALCE) | ALCE: citation quality evaluation for generated answers |
| 37 | [github.com/beir-cellar/beir](https://github.com/beir-cellar/beir) | BEIR: heterogeneous IR benchmark |
| 38 | [github.com/embeddings-benchmark/mteb](https://github.com/embeddings-benchmark/mteb) | MTEB: embedding model leaderboard and harness |
| 39 | [github.com/allenai/scifact](https://github.com/allenai/scifact) | SciFact: claim verification against evidence |

## Embeddings (10)

| # | Source | What it is |
| --- | --- | --- |
| 40 | [huggingface.co/BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3) | BGE-M3: dense + sparse + multi-vector in one model |
| 41 | [huggingface.co/intfloat/multilingual-e5-large](https://huggingface.co/intfloat/multilingual-e5-large) | multilingual-e5: solid multilingual baseline |
| 42 | [huggingface.co/Alibaba-NLP/gte-large-en-v1.5](https://huggingface.co/Alibaba-NLP/gte-large-en-v1.5) | GTE v1.5: fast, strong English retriever |
| 43 | [huggingface.co/jinaai/jina-embeddings-v3](https://huggingface.co/jinaai/jina-embeddings-v3) | Jina v3: long context, task-specific adapters |
| 44 | [huggingface.co/nomic-ai/nomic-embed-text-v1.5](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5) | Nomic v1.5: open, long context |
| 45 | [huggingface.co/answerdotai/ModernBERT-base](https://huggingface.co/answerdotai/ModernBERT-base) | ModernBERT: base for CourtListener's legal embedder |
| 46 | [github.com/stanford-futuredata/ColBERT](https://github.com/stanford-futuredata/ColBERT) | ColBERT: late interaction retrieval |
| 47 | [huggingface.co/colbert-ir/colbertv2.0](https://huggingface.co/colbert-ir/colbertv2.0) | ColBERTv2 weights |
| 48 | [github.com/UKPLab/sentence-transformers](https://github.com/UKPLab/sentence-transformers) | sentence-transformers: the standard embedding library |
| 49 | [sbert.net/](https://sbert.net/) | SBERT docs: training and evaluation recipes |

## Rerankers (5)

| # | Source | What it is |
| --- | --- | --- |
| 50 | [huggingface.co/BAAI/bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3) | BGE reranker v2-m3: multilingual cross-encoder |
| 51 | [huggingface.co/cross-encoder/ms-marco-MiniLM-L-6-v2](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L-6-v2) | MS MARCO MiniLM cross-encoder; current default |
| 52 | [github.com/AnswerDotAI/rerankers](https://github.com/AnswerDotAI/rerankers) | One API over many rerankers, for swapping |
| 53 | [huggingface.co/castorini/monot5-base-msmarco](https://huggingface.co/castorini/monot5-base-msmarco) | MonoT5: sequence-to-sequence reranker |
| 54 | [github.com/castorini/rank_llm](https://github.com/castorini/rank_llm) | LLM listwise/pointwise reranking (RankGPT, RankZephyr) |

## Lexical (7)

| # | Source | What it is |
| --- | --- | --- |
| 55 | [lucene.apache.org/](https://lucene.apache.org/) | Lucene: BM25 foundation for ES/OpenSearch/Solr |
| 56 | [github.com/castorini/anserini](https://github.com/castorini/anserini) | Anserini: IR toolkit, reproducible BM25 baselines |
| 57 | [github.com/castorini/pyserini](https://github.com/castorini/pyserini) | Pyserini: Python IR toolkit, sparse+dense |
| 58 | [github.com/naver/splade](https://github.com/naver/splade) | SPLADE: learned sparse retrieval |
| 59 | [github.com/thunlp/OpenMatch](https://github.com/thunlp/OpenMatch) | OpenMatch: unified sparse/dense retrieval research |
| 60 | [github.com/facebookresearch/DPR](https://github.com/facebookresearch/DPR) | DPR: dense passage retrieval, the reference implementation |
| 61 | [www.sqlite.org/fts5.html](https://www.sqlite.org/fts5.html) | SQLite FTS5: BM25 in a file, for tests and small corpora |

## Serving (23)

| # | Source | What it is |
| --- | --- | --- |
| 62 | [vespa.ai/](https://vespa.ai/) | Vespa: hybrid retrieval + ranking + serving in one engine |
| 63 | [github.com/vespa-engine/vespa](https://github.com/vespa-engine/vespa) | Vespa source |
| 64 | [docs.vespa.ai/](https://docs.vespa.ai/) | Vespa docs: ranking expressions, RRF, phased ranking |
| 65 | [qdrant.tech/](https://qdrant.tech/) | Qdrant: vector DB with hybrid and filtering |
| 66 | [github.com/qdrant/qdrant](https://github.com/qdrant/qdrant) | Qdrant source |
| 67 | [qdrant.tech/documentation/](https://qdrant.tech/documentation/) | Qdrant docs |
| 68 | [weaviate.io/](https://weaviate.io/) | Weaviate: hybrid search built in |
| 69 | [github.com/weaviate/weaviate](https://github.com/weaviate/weaviate) | Weaviate source |
| 70 | [milvus.io/](https://milvus.io/) | Milvus: large-scale vector DB |
| 71 | [github.com/milvus-io/milvus](https://github.com/milvus-io/milvus) | Milvus source |
| 72 | [github.com/pgvector/pgvector](https://github.com/pgvector/pgvector) | pgvector: vectors in Postgres, one database |
| 73 | [lancedb.com/](https://lancedb.com/) | LanceDB: embedded columnar vector store |
| 74 | [github.com/lancedb/lancedb](https://github.com/lancedb/lancedb) | LanceDB source |
| 75 | [www.elastic.co/elasticsearch](https://www.elastic.co/elasticsearch) | Elasticsearch: BM25 + kNN + RRF |
| 76 | [www.elastic.co/guide/en/elasticsearch/reference/current/knn-se](https://www.elastic.co/guide/en/elasticsearch/reference/current/knn-search.html) | ES kNN and hybrid search docs |
| 77 | [opensearch.org/](https://opensearch.org/) | OpenSearch: Apache-2.0 Elasticsearch fork |
| 78 | [typesense.org/](https://typesense.org/) | Typesense: typo-tolerant search, simple ops |
| 79 | [www.meilisearch.com/](https://www.meilisearch.com/) | Meilisearch: fast, lightweight search |
| 80 | [github.com/chroma-core/chroma](https://github.com/chroma-core/chroma) | Chroma: embedded vector store for prototypes |
| 81 | [github.com/apache/solr](https://github.com/apache/solr) | Solr: Lucene-based search server |
| 82 | [solr.apache.org/](https://solr.apache.org/) | Solr project site |
| 83 | [github.com/facebookresearch/faiss](https://github.com/facebookresearch/faiss) | FAISS: ANN index library |
| 84 | [github.com/nmslib/hnswlib](https://github.com/nmslib/hnswlib) | hnswlib: minimal HNSW index |

## Frameworks (13)

| # | Source | What it is |
| --- | --- | --- |
| 85 | [www.llamaindex.ai/](https://www.llamaindex.ai/) | LlamaIndex: ingestion + retrieval framework |
| 86 | [github.com/run-llama/llama_index](https://github.com/run-llama/llama_index) | LlamaIndex source |
| 87 | [haystack.deepset.ai/](https://haystack.deepset.ai/) | Haystack: pipelines, retrievers, evaluators |
| 88 | [github.com/deepset-ai/haystack](https://github.com/deepset-ai/haystack) | Haystack source |
| 89 | [ragflow.io/](https://ragflow.io/) | RAGFlow: deep document understanding + RAG engine |
| 90 | [github.com/infiniflow/ragflow](https://github.com/infiniflow/ragflow) | RAGFlow source |
| 91 | [onyx.app/](https://onyx.app/) | Onyx: self-hosted enterprise search with connectors |
| 92 | [github.com/onyx-dot-app/onyx](https://github.com/onyx-dot-app/onyx) | Onyx source |
| 93 | [github.com/SciPhi-AI/R2R](https://github.com/SciPhi-AI/R2R) | R2R: RAG engine with REST API |
| 94 | [github.com/Cinnamon/kotaemon](https://github.com/Cinnamon/kotaemon) | kotaemon: document chat UI + pipeline |
| 95 | [neuml.github.io/txtai/](https://neuml.github.io/txtai/) | txtai: embeddings database + workflows |
| 96 | [github.com/langchain-ai/langchain](https://github.com/langchain-ai/langchain) | LangChain: broad integration layer |
| 97 | [github.com/microsoft/autogen](https://github.com/microsoft/autogen) | AutoGen: multi-agent orchestration |

## Graph (5)

| # | Source | What it is |
| --- | --- | --- |
| 98 | [github.com/microsoft/graphrag](https://github.com/microsoft/graphrag) | Microsoft GraphRAG: entity graph + community summaries |
| 99 | [github.com/HKUDS/LightRAG](https://github.com/HKUDS/LightRAG) | LightRAG: lighter graph RAG |
| 100 | [github.com/OSU-NLP-Group/HippoRAG](https://github.com/OSU-NLP-Group/HippoRAG) | HippoRAG: personalized PageRank over a knowledge graph |
| 101 | [github.com/gusye1234/nano-graphrag](https://github.com/gusye1234/nano-graphrag) | nano-graphrag: small readable GraphRAG |
| 102 | [neo4j.com/docs/graph-data-science/](https://neo4j.com/docs/graph-data-science/) | Neo4j GDS: PageRank, PPR, community detection |

## Grounding (4)

| # | Source | What it is |
| --- | --- | --- |
| 103 | [github.com/Liyan06/MiniCheck](https://github.com/Liyan06/MiniCheck) | MiniCheck: efficient factual-error detection; 98.8% here |
| 104 | [huggingface.co/lytang/MiniCheck-RoBERTa-Large](https://huggingface.co/lytang/MiniCheck-RoBERTa-Large) | The MiniCheck checkpoint the app calls |
| 105 | [github.com/yuh-zha/AlignScore](https://github.com/yuh-zha/AlignScore) | AlignScore: alignment-based factual consistency |
| 106 | [github.com/potsawee/selfcheckgpt](https://github.com/potsawee/selfcheckgpt) | SelfCheckGPT: hallucination detection by sampling |

## Evaluation (7)

| # | Source | What it is |
| --- | --- | --- |
| 107 | [github.com/explodinggradients/ragas](https://github.com/explodinggradients/ragas) | RAGAS: faithfulness, context precision/recall |
| 108 | [github.com/truera/trulens](https://github.com/truera/trulens) | TruLens: RAG evaluation and tracing |
| 109 | [github.com/confident-ai/deepeval](https://github.com/confident-ai/deepeval) | DeepEval: pytest-style LLM assertions |
| 110 | [www.promptfoo.dev/](https://www.promptfoo.dev/) | promptfoo: prompt regression testing |
| 111 | [github.com/usnistgov/trec_eval](https://github.com/usnistgov/trec_eval) | trec_eval: the IR metric standard |
| 112 | [github.com/terrierteam/ir_measures](https://github.com/terrierteam/ir_measures) | ir_measures: IR metrics in Python |
| 113 | [github.com/AmenRa/ranx](https://github.com/AmenRa/ranx) | ranx: fast IR metrics, alternative to ir_measures |

## Observability (6)

| # | Source | What it is |
| --- | --- | --- |
| 114 | [phoenix.arize.com/](https://phoenix.arize.com/) | Arize Phoenix: LLM tracing and evals |
| 115 | [github.com/Arize-ai/phoenix](https://github.com/Arize-ai/phoenix) | Phoenix source |
| 116 | [langfuse.com/](https://langfuse.com/) | Langfuse: tracing, prompts, evals, self-hosted |
| 117 | [github.com/langfuse/langfuse](https://github.com/langfuse/langfuse) | Langfuse source |
| 118 | [opentelemetry.io/](https://opentelemetry.io/) | OpenTelemetry: the tracing substrate |
| 119 | [github.com/open-telemetry/opentelemetry-python](https://github.com/open-telemetry/opentelemetry-python) | OpenTelemetry Python SDK |

## Parsing (12)

| # | Source | What it is |
| --- | --- | --- |
| 120 | [github.com/docling-project/docling](https://github.com/docling-project/docling) | Docling: PDF/HTML to structured docs (MIT) |
| 121 | [github.com/Unstructured-IO/unstructured](https://github.com/Unstructured-IO/unstructured) | unstructured: broad format ingestion |
| 122 | [github.com/VikParuchuri/marker](https://github.com/VikParuchuri/marker) | marker: PDF to markdown (GPL + RAIL weights) |
| 123 | [github.com/opendatalab/MinerU](https://github.com/opendatalab/MinerU) | MinerU: PDF extraction, strong on CJK |
| 124 | [github.com/pymupdf/PyMuPDF](https://github.com/pymupdf/PyMuPDF) | PyMuPDF: fast, reliable low-level PDF access |
| 125 | [github.com/adbar/trafilatura](https://github.com/adbar/trafilatura) | trafilatura: main-text extraction from HTML |
| 126 | [github.com/VikParuchuri/surya](https://github.com/VikParuchuri/surya) | Surya: OCR and layout detection |
| 127 | [github.com/PaddlePaddle/PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) | PaddleOCR: multilingual OCR |
| 128 | [tika.apache.org/](https://tika.apache.org/) | Apache Tika: format detection and extraction (JVM) |
| 129 | [github.com/kermitt2/grobid](https://github.com/kermitt2/grobid) | GROBID: structured extraction for scholarly PDFs |
| 130 | [github.com/explosion/spaCy](https://github.com/explosion/spaCy) | spaCy: NLP pipeline, sentence segmentation |
| 131 | [github.com/stanfordnlp/stanza](https://github.com/stanfordnlp/stanza) | Stanza: multilingual tokenisation and NER |

## Runtime (17)

| # | Source | What it is |
| --- | --- | --- |
| 132 | [github.com/vllm-project/vllm](https://github.com/vllm-project/vllm) | vLLM: high-throughput LLM serving |
| 133 | [github.com/huggingface/text-generation-inference](https://github.com/huggingface/text-generation-inference) | TGI: HuggingFace LLM serving |
| 134 | [github.com/huggingface/text-embeddings-inference](https://github.com/huggingface/text-embeddings-inference) | TEI: embedding/reranker serving |
| 135 | [github.com/triton-inference-server/server](https://github.com/triton-inference-server/server) | Triton: multi-model inference server |
| 136 | [github.com/ollama/ollama](https://github.com/ollama/ollama) | Ollama: local model runner |
| 137 | [github.com/ggerganov/llama.cpp](https://github.com/ggerganov/llama.cpp) | llama.cpp: quantised local inference |
| 138 | [www.ray.io/](https://www.ray.io/) | Ray: distributed compute, Ray Serve |
| 139 | [modal.com/](https://modal.com/) | Modal: serverless GPU |
| 140 | [github.com/bentoml/BentoML](https://github.com/bentoml/BentoML) | BentoML: model packaging and serving |
| 141 | [fastapi.tiangolo.com/](https://fastapi.tiangolo.com/) | FastAPI: current app framework |
| 142 | [github.com/tiangolo/fastapi](https://github.com/tiangolo/fastapi) | FastAPI source |
| 143 | [docs.pydantic.dev/](https://docs.pydantic.dev/) | Pydantic: schema validation |
| 144 | [github.com/huggingface/transformers](https://github.com/huggingface/transformers) | transformers: model loading |
| 145 | [github.com/huggingface/tokenizers](https://github.com/huggingface/tokenizers) | tokenizers: fast tokenisation |
| 146 | [pytorch.org/](https://pytorch.org/) | PyTorch |
| 147 | [github.com/redis/redis](https://github.com/redis/redis) | Redis: cache and vector search |
| 148 | [github.com/postgres/postgres](https://github.com/postgres/postgres) | PostgreSQL: relational store, tsvector, pgvector host |

## Security (2)

| # | Source | What it is |
| --- | --- | --- |
| 149 | [microsoft.github.io/presidio/](https://microsoft.github.io/presidio/) | Presidio: PII detection and anonymisation |
| 150 | [github.com/microsoft/presidio](https://github.com/microsoft/presidio) | Presidio source |

## Commercial (4)

| # | Source | What it is |
| --- | --- | --- |
| 151 | [www.westlaw.com/](https://www.westlaw.com/) | Westlaw: KeyCite citator, licensed |
| 152 | [www.lexisnexis.com/](https://www.lexisnexis.com/) | LexisNexis: Shepard's citator, licensed |
| 153 | [vlex.com/](https://vlex.com/) | vLex: international legal research |
| 154 | [www.fastcase.com/](https://www.fastcase.com/) | Fastcase: case law + citator, licensed |

## Not found

Three things were looked for and are absent from free sources:

- **A citator.** No free treatment data — whether a case was overruled, distinguished or followed.
  Westlaw's KeyCite and LexisNexis's Shepard's are the licensed options and are listed above.
- **County and municipal law in bulk.** Municode, American Legal and eCode360 each publish
  differently; JusticeDAO's normalized snapshot is municipal code with `authorizing_for_publication: false`.
- **A legal-specific open embedding model with published retrieval benchmarks.** Legal-BERT exists but
  predates modern retrieval training; the strongest available option is a general model (BGE-M3,
  ModernBERT) or a commercial legal embedding.

