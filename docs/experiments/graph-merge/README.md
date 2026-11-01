# Does fixing the graph merge change the results?

Yes, mechanically. No, not in a way that justifies shipping it.

## What was tried

`pipeline.py` appends graph neighbours to `pool` but never enters them into `fused`, so `final_score` gives them `0.0` and they sort below every hybrid candidate before the cut to `k`. With the hybrid stage returning 83 candidates and `k` capped at 50, an addition sits at rank 84 or lower and is unreachable.

The experiment added a `GRAPH_SLOTS` environment variable: when greater than zero, the top N graph additions are moved into the ranked head at `GRAPH_INSERT_AT` (default 10) before the cut. Default `0` reproduces the previous ordering exactly, so the change is inert unless asked for.

The patched code ran as a second engine instance on port 8013 against the same corpus (`octo-chunk:804646`) and graph (`5f469d7d`), and twenty development questions were captured with `GRAPH_SLOTS=5` and compared to the production capture with it unset.

## Result

| Measure | Result |
| --- | --- |
| Queries whose top-12 changed | **5 of 20** |
| Queries whose full list changed | **5 of 20** |
| New documents introduced | 18 |

The five queries that changed are exactly the five that had graph additions, which confirms the mechanism does what it claims: the graph becomes visible at the position it was inserted.

## Why it should not be enabled on this evidence

The inserted documents are the graph's actual one-hop neighbours, and they read as topical drift rather than answers. For the question *"What did the court decide about the property issue?"*, the hybrid head ends with a tax case, and the graph then contributes:

```
rank 11  Helvering v. Grinnell
rank 12  Griffiths v. Commissioner, 308 U.S. 355
rank 13  Abbott Laboratories v. Gardner, 387 U.S. 136
rank 14  Keystone Bituminous Coal Ass'n v. DeBenedictis
rank 15  Lucas v. South Carolina Coastal Council
```

`Abbott Laboratories` is an administrative-procedure case and `Helvering`/`Griffiths` are tax cases; they arrive because the graph followed citation edges out of a tax case that mentioned property, not because they bear on the question. `Lucas` and `Keystone` are genuine takings cases and may be reasonable, which is the honest complication: some of what the graph adds looks useful and some does not, and nothing in this experiment distinguishes the two.

So the merge fix makes the graph visible and what becomes visible is mostly noise for these questions. Enabling it would trade a deterministic hybrid ranking for one contaminated by citation proximity.

## What this means

The graph is not being unfairly suppressed by the merge order alone. Fixing the order is necessary but not sufficient: the expansion has no relevance filter, so a one-hop neighbour of a highly-ranked case is admitted regardless of whether it answers the question. A useful graph contribution needs either a scoring signal on the neighbours or a relevance gate on what enters, and that is a larger change than moving items in a list.

## Status

The engine was left at its baseline commit. The patch is not applied, `GRAPH_SLOTS` does not exist in the deployed code, and the production service was never restarted, so ranking behaviour is unchanged. The 15-line patch and the captured data are described here so the experiment can be repeated if a relevance gate is added later.
