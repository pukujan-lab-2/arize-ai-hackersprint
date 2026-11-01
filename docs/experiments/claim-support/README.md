# Claim-support: MiniCheck vs JEV vs GLiNER

Eighty labelled claim-and-passage pairs, scored by three judges on identical inputs. Raw data is in `pairs.json` and `results.json` beside this file.

## Method

Pairs are built from real Colorado passages in the pooled retrieval candidates, so the passages are the corpus the product actually cites.

| Kind | Count | Construction | Label |
| --- | --- | --- | --- |
| positive | 30 | a sentence from the passage, paired with its own passage | supported |
| negative | 30 | that sentence paired with a passage from a different case | unsupported |
| hard negative | 20 | the sentence with one four-digit year changed by three years | unsupported |

Labels are true by construction rather than by judgement, which is the point: a set labelled by opinion measures the labeller. The hard negatives are the weak ones — changing a year in a sentence about pasturage may not change whether the passage supports it, and two judges did accept some of them.

Every passage is cut to 350 words before scoring, roughly the 512-token limit the encoder judges accept, and the same cut is used for all three. Prompts are the same shape for all three: the claim and the passage, nothing else.

## Results

| Scorer | TP | FN | FP | TN | Precision | Recall | F1 | Accuracy | ms/pair | $/1k pairs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MiniCheck (`lytang/MiniCheck-RoBERTa-Large`) | 29 | 1 | 0 | 50 | **1.000** | 0.967 | **0.983** | **0.988** | 332 | 0 |
| JEV (`typesafe/jev-1.14`) | 30 | 0 | 2 | 48 | 0.938 | **1.000** | 0.968 | 0.975 | **191** | 0.023 |
| GLiNER (`fastino/GLiNER2.5-Decide`) | 20 | 10 | 30 | 20 | 0.400 | 0.667 | 0.500 | **0.500** | 1445 | 0 |

- **TP** supported and accepted, **FN** supported and rejected, **FP** unsupported and accepted, **TN** unsupported and rejected.
- Latency is per pair on the machine each runs on, so it is not a like-for-like comparison: MiniCheck and JEV are measured on the VPS, GLiNER on the Windows host on CPU.
- JEV cost is measured, not estimated: $0.001849 for 80 pairs.

## What it means

**GLiNER is at chance.** It accepted 30 of the 50 unsupported pairs and rejected a third of the supported ones. Accuracy is 50.0% on a balanced set, which is what a coin flip scores. Its published judge benchmark is near chance, and this reproduces that on this corpus. It is also the slowest by a wide margin and still got the answer wrong. Do not use it as a support judge.

**MiniCheck never raised a false alarm.** Zero unsupported pairs accepted, one supported pair rejected. If the cost of wrongly rejecting a grounded answer is higher than the cost of missing an ungrounded one, it is the right choice, and it needs no external service or budget.

**JEV found every supported pair** and missed two hard negatives. It is the fastest per pair and the only one with a per-call cost, which at $0.023 per thousand pairs is negligible for this volume.

**Neither MiniCheck nor JEV is the reason answers fail the safeguard.** Both call correctly-supported passages supported, so the failures measured elsewhere are about the claims being checked, not the judge's ability. That was the open question this experiment was built to answer, and the answer is that the judges are fine.

## Caveats

- Constructed pairs are easier than real answers: a sentence lifted from its passage is a favourable case, and a real answer's prose summary is not.
- The 20 hard negatives are not all genuinely unsupported, so the two JEV misses may be labels that are wrong rather than judgements that are wrong.
- One run of each scorer, no repeats, so the intervals on these numbers are wide even where the gap is large.
- GLiNER ran on CPU on the Windows host; its latency would improve on a GPU but its accuracy would not change.
