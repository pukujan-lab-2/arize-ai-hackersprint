# Pipeline quality

What the question-to-answer path does today, how it is measured, and what is still weak. Written after the gun-license
failures of 2026-11-04 (a question about gun licences returned driver's, liquor and contract licence cases, and the
citation checks failed). The issues are #58 to #64.

## What changed in the pipeline

- **Follow-ups** are rewritten into a standalone query by the model, with a plain fallback (#61). "I meant a gun
  license" no longer searches for the word "meant".
- **Relevance gate** (#62): when the reranker ran, the best passage's score decides if the question is on point
  (`RELEVANCE_MIN_TOP_SCORE`, default 1.0) and passages below `RELEVANCE_FLOOR_SCORE` (default 0.0) are not offered
  as authorities. Without a rerank stage the old word-overlap rule applies. An off-corpus question gets the "no
  authority" answer, which the safeguard passes without checking.
- **Query expansion** (#72): everyday firearm and licence wording is searched together with the statutes' vocabulary.
- **Support check** (#58, #70): quotes that differ only by curly punctuation count as verbatim; every `[n]` on a
  sentence is checked against its passages; markup and the "Short answer:" label are stripped from the claim.
- **Tracing** (#60): LLM spans carry the model name and provider; safeguard, support, citation guard and groundedness
  are posted to Phoenix as span annotations (`app/tracing.py`, retried because the span lands first).
- **Statutes** (#63): `tools/crs_chunks.py` parses the General Assembly's official title text into chunks and
  `tools/crs_load.py` writes the SQL that adds them to the legal index, every row tagged so a rollback script removes
  exactly what was added. Loaded so far: C.R.S. 18-12 (the 2024 uncertified printout). No embeddings; the engine embeds at
  query time. Check the site's reuse terms before widening this.
- **Legal engine** (legal-engine#4): cases the graph adds are fused into the ranking instead of appended after it.

## Measuring it

`tools/phoenix_eval.py` runs the cases in `tools/phoenix_cases.py` through the pipeline and records a Phoenix
experiment, so runs can be compared side by side:

    PHOENIX_URL=http://<phoenix>:6006 PHOENIX_SECRET=... python tools/phoenix_eval.py --dataset precedent-legal --name <label>

Datasets: `precedent-legal` (10 dev cases, including the gun-licence conversation) and `precedent-legal-holdout` (6
cases kept out of tuning). Code evaluators: answers on topic, on-topic citations, no wrong-subject citations, support
check, citation guard, refuses off-topic. `--judges` adds four LLM judges from `tools/phoenix_judges.py`. Run it on a
copy of the app with `OCTO_TRACES=off` so experiment traces stay out of the production project.

| experiment | support | wrong-subject | refuses off-topic |
|---|---|---|---|
| deployed baseline | 0/8 | 2/4 | 1/2 |
| + relevance gate, rewrite, support fixes | 2-3/8 | 2/4 | 2/2 |
| + statutes loaded | 3/8 | 2/4 | 2/2 |
| + query expansion | 1/8 | 4/4 | 2/2 |

## Known weak spot

The support check scores the answer as its weakest sentence. Correct gun-licence answers now cite the right statutes,
but a summary sentence that spans several authorities scores low on its own and pulls the whole answer under 0.5, so
the check abstains on most answers. Options on the table: average the sentence scores, or exempt descriptive sentences.
Both let some weakly supported answers through, so this is a product call, not a bug fix.

## The legal engine's deploy

The engine (`~/apps/legal-engine` on the VPS, port 8011) is deployed from `pukujan-lab-2/legal-engine` `main`. A
Komodo action pulls the repo every 5 minutes into `~/apps/legal-engine-src` and runs the repo's `deploy/vps/deploy.sh`,
which copies the code into the install, keeps the previous code, rolls back if the new code does not compile, and
stops the idle engine so its next request starts on the new code. Details and the resource are in
`pukujan-lab-2/server-management` (`vps/legal-engine/README.md`, `komodo/resources/legal-engine.toml`).
