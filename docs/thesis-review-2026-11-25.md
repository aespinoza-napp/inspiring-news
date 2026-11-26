# Thesis review — 25 November 2026

An estimate of the mark this thesis would get, what drives it, and what to
change to raise it. It assumes UPC's 0–10 scale (the thesis cites FIB and the
MDS regulations). It is an informed guess, not a committee's opinion: no
rubric or director's feedback was read. Every figure is from a committed
record: `docs/thesis-defense-brief.md` (3 Nov), `docs/audit-2026-10-28.md`,
`docs/decisions/evaluation.md`,
`backend/data/evaluation/experiments/verifier/averitec-balanced.md`,
`backend/data/evaluation/experiments/averitec/web-balanced.md` and
`docs/final_document/`.

---

## 1. The estimate

| State | Mark | Range |
|---|---|---|
| Defended as the document stands today | **≈ 6.5** | 6–7 |
| Finished the way §4 below plans | **≈ 8** | 7.5–8.5 |
| Ceiling, with a strong defence and §4 done well | ≈ 9 | — |

The committee grades **the document and the defence, not the repository**.
Most of the gap between 6.5 and 8 is the document lagging the work. Very
little of it is work still to be built.

---

## 2. What holds it down today

### 2.1 The document is behind the work
- **29 `\pending` placeholders** (§5 lists them): 15 in Results, 6 in
  Conclusions, one in the abstract.
- `main.pdf` was last built on **28 Oct**.
- **AVeriTeC is not in the Results yet.** It has been the benchmark since
  5 Nov, but chapter 7 only has a 10-claim comparison
  (`07-results/06-model-comparison/04-framework-comparison.tex`). None of
  the later results are in the document:
  - first 100 dev claims: the 3B gets **54.0 % [44, 64]**, against
    **58.0 %** for always answering Refuted;
  - the balanced 40, same evidence for every verifier (always-Refuted: 10):
    gpt-oss-120b 18, qwen3.5 9B 13, MiniCheck 11, llama3.2 3B 10;
  - the balanced 40 on the web, 3B: checkable plan 15, questions 12,
    plain 11.

### 2.2 The custom set's labels can no longer be reviewed
108 of the 139 labels are AI labels nobody reviewed. Since 17 Nov the set
is frozen and the labeller removed, so **they never will be**. Every
custom-set figure in chapters 7 and 9 rests on them. About 11 placeholders
wait for "the reviewed labels" or "the labelling tool's time per fact"
(§5, group B). Those can't be filled as written: they have to be
**reworded**.

### 2.3 Three of the four research questions are thin
- **RQ1 (finding):** discovery and trending were measured on one day of
  five each.
- **RQ3 (person vs model):** no person in it yet. The only agreement figure
  is the pipeline against itself (κ 0.84 on 14 claims).
- **RQ4 (how much of the job):** no time per fact; 0 of 139 timed.

### 2.4 Chapter 8 doesn't cover the Devastating edition
Chapter 8 is complete otherwise (~3,300 words: sustainability, data
ethics, equity and bias, inclusive language, SDGs). It never mentions the
Devastating edition, which handles terrorism, suicide, mass killing and
racism with fact-checking switched off. A committee member who sees it in
the demo will ask about it first.

---

## 3. What the mark rests on

### 3.1 Why it can reach 8
- **Rigour well above a typical master's thesis.** Decision rules written
  before the runs; paired differences with intervals; replay on fixed
  evidence (`cli run --replay`; 10 of 10 verdicts identical); a temporal
  gate on AVeriTeC evidence. Negative results kept, not hidden: the IPTC
  topic classifier (30 vs 46 of 56), the fast profiles (−17 points), Laya.
- **One clear finding you can defend.** The search comes within
  **2.9 points [−17.1, +11.4]** of the annotator's own evidence pages, and
  32 of 34 errors are the model's reasoning. AVeriTeC confirms it on fixed
  evidence: a stronger model on the same pages scores **+20 points
  [+5, +35]** over the 3B. *The model is the limit, not the retrieval.*
- **Traceability you can show on screen.** The lake's lineage, the job
  journal and `/trace` answer "how do I know where this verdict came from"
  live in three minutes (`thesis-defense-brief.md` §5).

### 3.2 Why it stays below 9
- **The headline accuracy is at or below a trivial baseline.** The 3B is
  4 points under always-Refuted on the first 100 dev claims, and equal to
  it on the balanced 40. With 40 claims the intervals are about ±15
  points, so most comparisons can't tell the options apart. That's an
  honest result, but a hard one to get a 9 on.
- **Breadth built after the 14 Oct freeze**: writing, trends, the graph,
  the two editions, packages, the WordPress import, the Universe. If the
  thesis presents these as contributions, they read as scope drift.
- **Authorship and references.** Much of the text was drafted by AI from
  the records (audit T7). The 31 references written from memory were
  never re-checked (T8; `references.bib` has 64 entries now). One invented
  reference costs more than any missing result.
- **Length.** About 69,000 words across chapters 1–9, 157 pages on
  28 Oct. A committee reads the first chapters, the results and the
  conclusions closely, and skims the rest. Chapters 5 (~15,900 words) and
  6 (~13,200) are where to cut.

---

## 4. What to do, in order of how much it moves the mark

### 4.1 Rebuild chapter 7 around AVeriTeC *(largest gain)*
- [ ] One results table: accuracy, **macro-F1**, **always-Refuted** beside
      every row, 95 % intervals, seconds per claim, self-hosted yes/no.
- [ ] Two conditions: **fixed evidence** (verifiers: 3B, 9B, MiniCheck,
      gpt-oss-120b) and **web** (plans: plain, questions, checkable).
- [ ] Say once that **no verifier can answer Conflicting**, so the ceiling
      on the balanced set is 75 % (MiniCheck: 50 %).
- [ ] Say what AVeriTeC does not cover: English only, politics and health,
      no constructive or Spanish news.
- [ ] **Demote the custom set** to a *development set with unreviewed AI
      labels*. Keep its figures for what they show (oracle vs search,
      stage attribution, replay determinism), not as headline accuracy.
- [ ] Rewrite the abstract's pending block (`frontmatter/abstract.tex:55`)
      on the AVeriTeC figures.
- [ ] *Optional, your call:* run more of the balanced set (35 per label,
      140 in all) to narrow the intervals. That breaks the 10-claims-a-run
      rule, so it needs your decision.

### 4.2 Give RQ3 a person, or narrow it in writing
- [ ] **Selection is now measurable.** `/discover` records your own five
      blind, then the AI's five from the same list, and computes precision,
      recall, Jaccard and κ (commit `0163ff2`, 24 Nov). Ten rounds, about
      15 minutes each, fill `04-rq3-person-and-model.tex:42` and give RQ3
      a real person-vs-model figure.
- [ ] If you can't do the verdict-side blind re-label (the labeller is
      gone), **narrow RQ3 to selection** in §1.5 and say why. That's better
      than leaving its placeholders empty.

### 4.3 Reword the placeholders that wait for reviewed labels
- [ ] For each placeholder in group B (§5), replace "on the reviewed
      labels" with what *is* known. Then say once, in Threats to Validity,
      that the labels stayed unreviewed and why.
- [ ] **RQ4:** with no time per fact, answer the question as one of
      extent: which stages run unattended, at what quality, and where a
      person is still needed. Report the AI's seconds per claim (measured)
      and say the person's time was not measured.

### 4.4 Label every feature as evaluated, demonstrated or future work
- [ ] **Evaluated:** the fact-checking pipeline, the verifiers, the search
      plans, the topic classifier (negative).
- [ ] **Demonstrated:** writing and the draft check, the graph, `/trace`,
      the reader, the Universe.
- [ ] **Future work:** trends, Laya (as a written negative result), the
      recommendation system and mobile app (`resumen-ejecutivo.md`),
      deployment to Google Cloud ("deployment-ready, not deployed").
- [ ] Put the three lists in §1.6 (scope) so the committee reads them
      before chapter 5.

### 4.5 Chapter 8: the Devastating edition as a contrast condition
- [ ] One section: the same discovery, selection and writing, with no
      claim checked. Its purpose is to show what the fact-check stage is
      for.
- [ ] Cite reporting guidelines for its topics, the WHO's on suicide in
      particular. Say what keeps it from harm: never public, a separate
      graph, every output labelled **Not checked**, the persona dropped for
      suicide and self-harm.
- [ ] Keep it out of every accuracy figure, and say so once.

### 4.6 Authorship and references
- [ ] Disclose the AI assistance plainly (where the faculty asks for it,
      or in the acknowledgements and §3.1 tools).
- [ ] Rewrite the drafted results and discussion in your own words. The
      committee will ask about them, and the answers have to be yours.
- [ ] Open every entry in `references.bib` once and check its authors,
      year and title.

### 4.7 Your own placeholders (only you can write them)
- [ ] Budget (personnel, hardware, total), director meetings, milestone
      dates, the objectives' final status, final remarks, acknowledgements
      (§5, group A).

### 4.8 Cut
- [ ] Move implementation detail from chapters 5 and 6 into appendices,
      or remove it: anything a committee member doesn't need to follow
      chapter 7.

---

## 5. The 29 placeholders, by what they need

Paths are under `docs/final_document/`. The grouping is a reading of each
placeholder's text, so check each one when you open it.

### A. Only you can write these (8)
| Where | What |
|---|---|
| `chapters/03-project-management/01-methodology/05-tools.tex:20` | follow-up meetings with the director |
| `chapters/03-project-management/02-planning/04-milestones.tex:29` | official milestone and delivery dates |
| `chapters/03-project-management/05-budget/01-personnel-costs.tex:45` | gross hourly cost per role, with its source |
| `chapters/03-project-management/05-budget/02-hardware-software-costs.tex:21` | the laptop's price and amortised cost |
| `chapters/03-project-management/05-budget/04-contingency-total.tex:20` | the budget total |
| `chapters/09-conclusions/02-objectives-achieved.tex:55` | each objective's final status |
| `chapters/09-conclusions/05-final-remarks.tex:9` | personal assessment |
| `frontmatter/acknowledgements.tex:8` | acknowledgements (optional) |

### B. Wait for reviewed labels that will never come: reword (11)
| Where | What it waits for |
|---|---|
| `chapters/07-results/04-rq3-person-and-model.tex:27` | κ between the AI pass and the annotator |
| `chapters/07-results/04-rq3-person-and-model.tex:80` | the annotator's blind re-label of 14 claims |
| `chapters/07-results/04-rq3-person-and-model.tex:89` | κ of the pipeline against reviewed labels |
| `chapters/07-results/05-rq4-system.tex:55` | the four RQ4 figures on reviewed labels |
| `chapters/07-results/05-rq4-system.tex:70` | time per fact from the labelling tool |
| `chapters/07-results/07-pre-verdict-stages.tex:63` | the topic classifier on reviewed labels |
| `chapters/07-results/08-discussion.tex:79` | the discussion of RQ1, RQ3, RQ4 on the custom set |
| `chapters/09-conclusions/01-rq-answers.tex:53` | RQ2 settled on reviewed labels |
| `chapters/09-conclusions/01-rq-answers.tex:62` | κ, AI pass vs annotator |
| `chapters/09-conclusions/01-rq-answers.tex:77` | RQ4 on reviewed labels, and time per fact |
| `frontmatter/abstract.tex:55` | the custom-set results: rewrite on AVeriTeC (§4.1) |

### C. Still measurable: a run, or some of your time (10)
| Where | What | Needs |
|---|---|---|
| `chapters/07-results/04-rq3-person-and-model.tex:42` | ten blind and ten assisted selection rounds | your time; the tool exists (§4.2) |
| `chapters/09-conclusions/01-rq-answers.tex:23` | RQ1 settled on your own labels, two rounds or more | your time |
| `chapters/07-results/02-rq1-finding.tex:137` | discovery days 2–5 | your time, 15 min a day |
| `chapters/07-results/02-rq1-finding.tex:182` | trending days 2–5 | your time, 15 min a day |
| `chapters/07-results/03-rq2-verifying.tex:256` | pooled precision, recall and reciprocal rank | judging the pooled pages (U2) |
| `chapters/07-results/07-pre-verdict-stages.tex:43` | admission over ≥100 round candidates | a run |
| `chapters/07-results/07-pre-verdict-stages.tex:76` | source probe weeks 2–4 | a run per week |
| `chapters/07-results/07-pre-verdict-stages.tex:113` | admission's time, one ingestion round end to end | a run |
| `chapters/07-results/06-model-comparison/02-writing-models.tex:96` | the 4B writer re-run, the 9B | a run |
| `chapters/05-development/11-news-map.tex:102` | 60 fps while panning and zooming | one measurement |

If time is short, the C items worth doing first are the selection rounds
(they give RQ3 a person) and discovery days 2–5 (they turn RQ1 from a
demonstration into a measurement). The rest can be reworded as future work
and lose little.
