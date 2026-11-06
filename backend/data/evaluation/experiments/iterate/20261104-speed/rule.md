# The iteration loop's rule (version 1)

Written by `cli iterate init` before any try. Editing this file ends the
campaign: `score` refuses to decide against a rule that changed.

Every try is compared, paired claim by claim, with the campaign's
**baseline** (the defaults replayed on the evidence run, try 0), never with
another try. Counts are in claims of the paired set.

## Valid at all

- The run is over the campaign's claims (same dataset file, the train
  half), with the label, model and thresholds `propose` recorded, and - for
  a replay - replays the campaign's evidence run.
- It sets apart (error, not checked, search unavailable) at most
  1 claim(s) more than the baseline does on the same claims.
  A claim set apart drops out of both sides of the comparison, so without
  this a try could improve its accuracy by giving up on its hard claims.

## The screen (the first claims only)

A try is first run on the first `screen` claims. It is **screened out**
when it gets 3 or more claims wrong that the baseline got
right, net, or when its median claim is 1.5x the baseline's
with no claim gained. Otherwise it runs on every claim (the same run,
resumed).

## The decision (every claim)

Quality, against the baseline:

- **better**: the paired accuracy difference's 95% interval is above zero
  and it is confidently wrong (a definitive verdict that is not gold) no
  more often;
- **worse**: 2 or more claims wrong net, or confidently wrong
  more than 1 more time(s);
- **same**: anything else ("no detectable difference" is a result).

Speed: **meets the target** when a claim's median is at most
20 s and its 90th percentile at most 30 s (the
campaign may set others); **faster** when the median is at most
0.9x the baseline's. A replay's seconds are its own plus what
retrieval took for that claim in the evidence run.

**Keep** when better, or when the same, at most 1 claim
lost net, confidently wrong at most 1 more, and
faster or meeting the target. **Reject** otherwise.

## Searched tries

A try the replay cannot see (what is searched, how many pages, the claim
restated, the second look, the deadline, or code on the search side) is
run with its own search. It is compared with **two searched baselines**
made back to back in the same window, and the gap between them (claims
wrong net) is the noise: it is **better** only when better against both and
its net gain exceeds that gap; **worse** when worse against both. Its
seconds are its own, as measured.

## The end

The campaign stops when its tries are spent or a kept try meets the target.
Nothing a campaign keeps becomes a default: the best kept try goes to the
test half once, run by the author, and is adopted only if it holds there
(the `fact-check-change` skill).
