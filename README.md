# Precedent

Picture an associate with twenty minutes before a call and one question: *can police search a car without a warrant in Colorado?* A chatbot answers in seconds, and one of its five cases doesn't exist. Nobody notices until opposing counsel does.

**Precedent writes short research memos where every citation comes from cases it actually retrieved.** You ask a question, four agents split the work, and a final check refuses any draft that cites something outside that set. It's built for law firms and in-house legal teams who want a fast, cited first pass they can verify.

Live at **https://arize.design-bakery.com**.

## What you get from one question

- **A memo of about 150 words**: a short answer, three or four key authorities with a quote from each, and a caveat on jurisdiction and facts.
- **The citations behind it**, with court, date and the passage each one was pulled from.
- **A citation map** (`/map`) that shows the retrieved cases and how they cite each other, with an optional narrated tour.
- **Follow-up questions** that reuse the earlier answer and its authorities.
- **Voice in and out**: ask by microphone and listen to the memo. Speech comes from Fish Audio, then ElevenLabs if it's configured, then a local Kokoro server, and finally the browser's own voice, so the tour keeps talking when a provider is capped or down.

Every answer carries the same line: *this is an AI-generated research summary, not legal advice.*

## How the four agents work

**Each agent claims a seat, does one job, logs it, and hands off.**

1. **Planner** takes the question. For a follow-up it asks the model to rewrite it into a standalone query (it falls back to the question plus the earlier one if the model is down), then dispatches the others.
2. **Retriever** finds seed authorities in the case graph, pulls matching passages from the legal engine (BM25, dense, graph and a cross-encoder rerank over cases and Colorado statutes), expands one hop along citations, and ranks the results by citation-weighted PageRank. Everyday wording is also searched with the statutes' own words ("gun license" adds "firearm, concealed handgun, permit"). If the best reranked passage scores too low, the question is treated as off-corpus and gets an honest "no authority" answer instead of the nearest wrong cases.
3. **Answer** drafts the memo from those numbered authorities only. It tries InferHub first, then Anthropic, and if both fail it returns a plain template that lists the authorities instead of making something up.
4. **Safeguard** checks the draft. Every `[n]` must point at a retrieved authority, any citation-shaped string must be one it was given, and sentences without a citation are flagged. A draft with no citations fails. A support check (MiniCheck, in the legal engine) then scores each sentence against every passage it cites; the weakest sentence sets the answer's score, and a score under 0.5 is reported as unsupported. An answer that says there is no authority passes without that check.

**Every step is written down.** Each run gets a folder under `runs/<run_id>/` with an event log and the final result, and the seats are recorded in `.coord/assignment.json`. Steps are also traced to Arize and Phoenix, where the safeguard, support, citation guard and groundedness scores are posted as span annotations. Prompt-level quality is measured with datasets and experiments in Phoenix; see `docs/PIPELINE_QUALITY.md`.

## Where it stops

- **The safeguard checks citations, not legal reasoning.** It catches a made-up or out-of-set case. It can't tell whether a quote is a fair reading of the holding.
- **The support check is strict.** Taking the weakest sentence means one vague summary sentence can pull a correct, well-cited answer under 0.5. This is known and measured; see `docs/PIPELINE_QUALITY.md`.
- **Statutes are partial.** Only C.R.S. Title 18, Article 12 (the 2024 uncertified printout) is loaded so far. Those chunks have no embeddings; the engine embeds them at query time.
- **The case data isn't in this repo.** The graph (`data/nodes.jsonl`, `data/edges.jsonl`) and the Octo passage snapshot live on the host that runs the app. Without them a run stops early and says the data isn't loaded.
- **Answers are capped and rate-limited** (questions per minute, hourly model and voice caps), so a busy demo can fall back to the template or to the browser's own speech.

## Run it yourself

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn app.server:app --port 3000
```

Then open http://localhost:3000. The older `uvicorn server:app` still works.

The app serves the built frontend, so build it once before starting the server:

```bash
cd web && pnpm install --frozen-lockfile --ignore-workspace && pnpm build
```

Without that build the pages return an error rather than an older frontend; there is only one frontend.

Set these in your shell or a local `.env` file, and never commit them:

- `INFERHUB_API_KEY`, `ANTHROPIC_API_KEY`
- Tracing needs no extra keys: spans go to Octo (`OCTO_API_KEY`, `OCTO_WORKSPACE_ID`) and on to its Phoenix. `OCTO_TRACES=off` turns it off.
- `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`
- `OCTO_API_KEY`, `OCTO_WORKSPACE_ID`, `OCTO_BASE_URL`
- `FISH_API_KEY` and `FISH_VOICE_ID` for Fish Audio, if you use it
- `GRAPH_DATA_DIR`, if the case data isn't in `data/`

`LLM_MODE=fake` runs everything offline with no model calls, which is what the tests use.

## What's in the repo

| Path | What it holds |
|---|---|
| `app/` | The backend package: `server.py` (FastAPI app and routes), `agents.py` (the four agents), `llm.py` (model chain), `graph_store.py` (SurrealDB with a NetworkX fallback), `octo_retriever.py`, `ttschain.py` (voice chain, queue and clip cache), `octocache.py` (shared Octo cache layer), `coord.py`, `contracts.py` |
| `schema/`, `migrations/` | The versioned data model for the tables the app keeps in Octo, and numbered SQL migrations that the deploy applies |
| `acs/` | Agent coordination: the task board, the `claim.py` CLI and the hot-loader, plus the vendored ACS runtime |
| `web/` | The frontend: source in `web/src/`, build root in `web/package.json`. Built on the serving machine from the deployed commit; the output is not committed |
| `contracts/` | `openapi.json` for the API, one contract per agent role in `agents/`, and `storage.json`, which says where each kind of data lives |
| `tests/`, `ci/` | The test suite, offline triage helpers and `docs_refresh.py` (decides when the docs are due for a refresh) |
| `deploy/` | The deploy script, the launchd wrapper and plists for the host |
| `tools/` | `run_all.sh`, `ci_local.sh`, the adoption and dependency checks, the Kokoro installer and Arize helpers; `phoenix_eval.py`, `phoenix_cases.py` and `phoenix_judges.py` (Phoenix datasets and experiments); `crs_chunks.py` and `crs_load.py` (the statute loader) |
| `arize/` | Arize experiments and judge setup |
| `docs/` | Project notes and hackathon records, indexed in `docs/README.md`. The voice chain, the caches and the data model are explained in `docs/voice-and-data-model.md` |

`repo.manifest.json` lists every top-level path with its owner and where its runtime data lives. Coding agents should start with `AGENTS.md`.

## How changes ship

[![CI](https://github.com/Pukujan-lab/arize-ai-hackersprint/actions/workflows/ci.yml/badge.svg)](https://github.com/Pukujan-lab/arize-ai-hackersprint/actions/workflows/ci.yml)

Pull requests run the `gates` job: ruff, mypy, a compile pass, the tests, and the manifest and contract checks. PRs from the owner or a bot merge themselves with a squash once `gates` passes. A self-hosted runner on the host then runs `deploy/deploy.sh`, which moves the live checkout to `main`, restarts the app, checks `/api/health` locally and on the public URL, and rolls back if either check fails. It won't deploy over uncommitted changes on the host.

**Next step:** open https://arize.design-bakery.com, pick one of the sample questions, then open the map to see which cases the memo rests on.
