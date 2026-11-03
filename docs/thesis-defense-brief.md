# Thesis defence brief — 3 November 2026

What a committee will ask, what the project can answer today, where the
structure is weak, and what to do in the eight weeks left before the
paper sprint (Dec 25–31). Every figure below is from a committed record:
`docs/audit-2026-10-28.md`, `docs/decisions/evaluation.md`,
`docs/decisions/performance.md`, the label files in
`backend/data/evaluation/manual/` and the thesis sources in
`docs/final_document/`. Checked today: 108 of the 139 labelled facts
still say "not yet checked", and the thesis still has **28 `\pending`
blocks**.

---

## 1. The thesis in four sentences

1. A pipeline that finds constructive news by topic, selects the claims
   worth checking, searches the open web for evidence and asks a local
   language model for a verdict — every step recorded and traceable.
2. Four research questions follow the journalist's own sequence:
   **finding** (RQ1), **verifying** (RQ2), **person vs model** (RQ3),
   and **how much of the job the joined system takes over** (RQ4).
3. The measured answer so far: on the custom set's test half, a 3B local
   model reaches **51–53 % accuracy** (intervals about ±11 points). The
   per-source verifier cuts confidently wrong answers from **47 % to 29 %**,
   and the search comes within **3 points** of an annotator's own evidence
   pages. So **the reader, not the retrieval, is the limit**.
4. The system is a tool that a journalist supervises. It does not replace
   one. It is useful where it says "not checked" or "unverified" honestly,
   and a person is needed at selection and at every verdict it is unsure of.

If the defence leads with sentence 4, every weakness below becomes a
finding instead of a gap.

---

## 2. The questions a committee will ask, and today's honest answer

| # | Likely question | Answer today | Strength |
|---|---|---|---|
| Q1 | *Who labelled your ground truth?* | 139 facts, 70 test / 69 train, frozen 19 Oct. **108 are AI labels no person has reviewed.** | **Weak**: blocks every custom-set number |
| Q2 | *How accurate is the verification?* | 51.4 % [40.0, 62.9] per-source; 52.9 % [41.4, 64.3] list verifier; X-Fact pilot 29.7 % | Measured, but on unreviewed labels |
| Q3 | *Is the retrieval or the model the bottleneck?* | Search vs oracle pages: −2.9 points [−17.1, +11.4]. Stage attribution: 32 of 34 errors are reasoning (trace rule) | **Strong**: the most defensible result |
| Q4 | *Are the results reproducible?* | Same pipeline searched twice: 6–9 points apart. On fixed evidence the model is deterministic (10/10 replayed). `cli run --replay` exists | Good, if you explain the replay |
| Q5 | *How close are person and model (RQ3)?* | Only model-vs-itself: κ 0.84 on 14 claims. **The blind re-label of the 14 has not started; no blind/assisted selection rounds** | **Missing** |
| Q6 | *Does the retriever help a journalist find news (RQ1)?* | Discovery measured on 1 day of 5; trending on 1 day of 5; no round labelled by the author | **Thin** |
| Q7 | *So, does it replace a journalist (RQ4)?* | Coverage and confidently-wrong shares exist; time per fact: 0 of 139 timed | Partial; answer "no, here is where a person is needed" |
| Q8 | *Why a 3B model?* | CPU-only hardware; 9B tried on the same evidence (V3, V5); the model benchmark of 29 Oct per role | Fine, as a stated constraint |
| Q9 | *How do you know a verdict came from where you say?* | Three-layer lake with lineage, an append-only manifest, a job journal. **Since today, one page shows it all (Trace).** | **Strong**, and you can demo it |
| Q10 | *What about ethics, bias and harm?* | Chapter 8 exists. The Devastating edition (30 Oct) is kept **as a contrast, not for production** (your decision, 3 Nov), and chapter 8 does not cover it yet (§3, G7) | Fine once it is framed and written |
| Q13 | *How do you know the search worked when you measured?* | On 3 Nov Bing was found searching only the first word of each query. Fixed the same day. The full harness runs checked here, up to 30 Oct, look healthy (65–70 % of web titles share a claim word) (§3, G12) | Answerable, if you say it first |
| Q11 | *What did you not build that you promised?* | Recommendation system and mobile app (`resumen-ejecutivo.md`), cloud deploy (applied only to Floci) | State it as scope, not as delay |
| Q12 | *How much of the text did an AI write?* | Results text drafted from records in the 28 Oct session (audit T7); 46 references, 31 written from memory once (T8) | Disclose it; verify the references |

---

## 3. The structural gaps, ranked by how much of the defence they hold up

### G1 — The ground truth is not yet a ground truth *(critical, overdue)*
108 of 139 labels are the AI's own pass, so every custom-set figure in
chapters 7 and 9 rests on labels nobody has checked. U1 (review the 108,
blind re-label the 14) was due **30 Oct**. Nothing else on this list
matters as much: it unblocks 9 placeholders, RQ3, the headline-verifier
choice (N6) and the conclusions.

### G2 — The test half is small
70 test claims give intervals of about ±11 points, and the search's own
run-to-run noise (6–9 points) is as large as most effects measured. Most
comparisons cross zero (Laya, second look, fast profiles on test). **Do
not fix this by adding claims now.** Fix it in the text: report paired
differences with intervals (the harness already does), name the
minimum detectable effect, and present "no detectable difference" as a
result.

### G3 — RQ3 has no person in it yet
The only agreement figure is the pipeline against itself. RQ3 is a
person-vs-model question. It needs the blind re-label (κ annotator vs AI
pass, annotator vs pipeline) and, if time allows, the 10 blind + 10
assisted selection rounds. If the rounds do not happen, narrow RQ3 to
*verdicts only* and say so in §1.5.

### G4 — RQ1 rests on one day
Discovery and trending have 1 day of 5 each, and the source probe has
1 week of 4. Each remaining day is about 15 minutes of the author's time and
cannot be done by code. Without them RQ1 is a demonstration, not a
measurement.

### G5 — RQ4 is asked as "replace the journalist"
The data answers "which parts, at what quality, and where a person is
needed". The thesis already rewords RQ4 as a question of extent: keep
the conclusions in that frame. The missing piece is **time per fact**
(the labeller records it since 20 Oct, and no fact has been saved since).
Every reviewed label in U1 now also produces timing, so G1 feeds G5.

### G6 — More was built than was evaluated
After the 14 Oct freeze the project added the writing flow, rewriting,
publishing, trends, the Neo4j graph, Laya and the two editions. Each is
real engineering, and each has little or no measured result. The writing
benchmark sits at 1/36 (4B) and 15/36 (9B), and Laya is not in the thesis
at all (N1). A committee reads this as scope drift. **Freeze features
now.** In the thesis, give each addition one of three labels: *evaluated*
(the pipeline), *demonstrated* (writing, graph, trace), or *future work*
(trends, Laya as a written negative result, editions).

### G7 — The Devastating edition: a contrast, and it must read as one
**Your decision (3 Nov):** it stays in the system to be shown as a
contrast, and it is not for production. That can strengthen the thesis,
because it makes the thesis's own premise visible. The same pipeline runs
with verification switched off and an ironic voice switched on, and the
contrast shows what the fact-check stage is for. To make the committee
read it that way and not as a second product:

- **Name it as a contrast condition** in §1.6 (scope) and §4: the same
  discovery, selection and writing, with no claim checked, which is what
  `fact_check_skipped` and the reader's **Not checked** already record.
- **Give it its own section in chapter 8.** It handles terrorism, suicide,
  mass killing and racism, so cite the reporting guidelines for those
  topics (the WHO's on suicide in particular). Say what keeps it from
  causing harm: never deployed publicly, a separate graph, every output
  labelled not checked.
- **Keep it out of every accuracy figure.** It has no verdicts, so it
  belongs to no RQ2–RQ4 number. Say so once.
- **In the demo, show it after the Positive edition, for one article**,
  never first, and say plainly that it is a contrast condition.
- **Keep it switched off** wherever the site is reachable without the
  password (the reader is public).

### G8 — Reproducibility depends on two machines
The run records are split across the laptop and the desktop (N2), and
`runs/` is gitignored. Copy `runs/manual-test/` across before U2, and
archive the exact runs the thesis cites (Appendix D) so each table can be
regenerated.

### G9 — "Production" is unverified
The containers run full analyses locally, but `deploy/gcp/` has only
been applied to an emulator. Call it "deployment-ready, not deployed", or
apply it once. It is not worth more than a day.

### G10 — Authorship and references
Disclose the AI assistance (T7). Rewrite the drafted results paragraphs
in your own words. Open every one of the 46 references once (T8). A
committee member who finds one invented reference will discount every
other.

### G11 — The business documents promise more than the thesis
`resumen-ejecutivo.md` lists a recommendation system and a mobile app.
Make the thesis say plainly that they are future work, so nobody reads
them as unfinished deliverables.

### G12 — A search that answered, about the wrong thing *(found and fixed 3 Nov)*
Every claim of an HPV-vaccination article came back UNVERIFIED, citing
arXiv papers and dictionaries. Through SearXNG, from this machine, Bing
searched **only the first word** of each query. Google, Brave and Yep
were suspended, and "HPV" never reached a query (acronyms were below the
4-letter floor). Both are fixed: engines re-measured and changed,
acronyms made query terms (`docs/fact-checking-changes.md` §9). For the
thesis:

- The 7 full harness runs here (to 30 Oct) look **healthy**: 65–70 % of
  web evidence titles share a word with their claim, and 0–11 % are
  off-topic domains such as arXiv, DOI or dictionaries. It is a rough
  screen, not a measure of relevance. The 22 Oct runs
  are on the other machine: run `python scripts/evidence_on_subject.py`
  there before relying on them.
- Nothing measured whether results were *on the subject*. The source
  probe counted results, which is how this went unnoticed. Say it in
  threats to validity (§7.9), and treat it as a finding: a result count
  is not a health signal.
- Runs after 3 Nov use a different search. Compare across that date only
  by replay (`cli run --replay`).
- **The same article re-run after the fix** is the clearest example of
  RQ2's finding that the model, not the retrieval, is the limit. The
  evidence was now right (South Africa's health department, Statistics
  South Africa, The Lancet), and two claims came back TRUE at 97 %. But
  the 3B marked two sources as *contradicting* "Since October 2024, South
  Africa has adopted a single-dose HPV vaccination approach" while quoting
  that exact sentence from each, so the article came out FALSE and was
  withheld. Use it in the defence: on screen, Live shows the source, its
  quote and the stance side by side.

### G14 — Evidence that was not evidence *(found and fixed 3 Nov)*
Pages repeating the article's own sentence counted as outlets confirming it (12
of 69 train claims). They are now removed, and a page with the same sentence
but one changed detail makes the claim FALSE without the model. Replayed on the
train half: accuracy **-1.4 points [-7.2, +4.3]**, no detectable difference;
altered claims caught 4 -> 6 of 15; confidently wrong unchanged at 20. Two
things to say at the defence: the fix was adopted for validity, not for the
score, which it did not raise; and the gain on altered claims overstates the real
world, because they were made by changing a detail of a real sentence. **Every
figure in chapter 7 predates this**: run the final test half after the label
review, with this in place, and say which code each figure came from.

### G13 — What exactly a claim asserts *(raised 3 Nov)*
A sentence cut from its article often does not say who is speaking or
what is asserted. Reported speech is the clearest case: "Samuda argued
... it had spent 30 years among the most murderous countries" was searched
as `Samuda Jamaica "30"` and judged as a quotation. There is now an
optional step that restates each claim as one checkable statement before
the search (`docs/fact-checking-changes.md` §10), shown on Live, Analyze
and the reader as "What is checked". It is **off for the harness** and not
yet measured. For the thesis it is one clean experiment, and a good answer
to "how do you handle quotes?": the train half's reference-evidence
recall in a retrieval-only run, with and without it. It is a paired
comparison on the same claims and needs no model verdicts. Committees ask
about quotations and attribution, so mention the distinction even if you
don't measure it: verifying *that it was said* differs from verifying
*what was said*.

---

## 4. What to do now (3 Nov → 24 Dec)

**Rule for the eight weeks: no new features.** Bugs, measurements and
writing only.

| When | Do | Unblocks |
|---|---|---|
| **Week of 3 Nov** | **U1**: review the 108 AI labels in the labeller (timing is recorded as you go); blind re-label the 14; `python labeller/app.py join` | G1, G3, G5; 9 placeholders |
| Same week, daily, 15 min | Discovery days 2–5 and trending days 2–5 (one round a day, labelled by you); source probe weekly | G4; 3 placeholders |
| Same week, unattended | Resume V5 on the test half (stopped at 8/70) and the writing benchmark (1/36, 15/36) | §7.6 |
| Week of 10 Nov | Re-run the test half on the reviewed labels; decide the headline verifier once (N6); compute κ (annotator vs AI pass, vs pipeline) | RQ2–RQ4 numbers |
| Week of 10 Nov | Copy run records between machines (N2); judge the 603 pooled pages (U2) | RQ2 pooled retrieval |
| Week of 17 Nov | Decide the scope labels of G6; write Laya as a negative result (N1); write the Devastating edition up as a contrast condition with its own ethics section (G7); the search incident in threats to validity (G12) | Chapter 1.6, 7.7, 7.9, 8 |
| Before any new run | Check the 22 Oct runs' web evidence on the other machine (G12) | Trust in RQ2 |
| If time allows (Nov) | Retrieval-only train-half run with and without claim restatement (G13) | RQ2, a paragraph on quotations |
| Weeks of 24 Nov – 8 Dec | Discussion of RQ1, RQ3, RQ4; conclusions; threats to validity with the minimum detectable effect (G2) | §7.8, ch. 9 |
| Weeks of 8–22 Dec | Your own placeholders (budget, milestones, director meetings, objectives' status, final remarks, acknowledgements); rewrite the drafted text; check the references | G10; the last 9 placeholders |
| Last | Abstract | — |

---

## 5. A defence demo that answers Q9 on screen

The interface now joins the stages, so one article can be followed live
in about three minutes:

1. **Discover** — pick a topic group, *Find articles*, *Let the AI
   choose*. Each candidate shows its rank and its parts. *Analyse*. The
   "Sent to analysis" list links each pick to **Live** and to **Trace**.
2. **Live** — open the run (`/live?job=…`, which also works for a run from
   before a restart). For each claim it shows the queries, the sources, the
   ratings, the stances, the verdict, and where the seconds went.
3. **Trace** — paste the URL (or press `/` in the header from anywhere).
   It shows five stages: *discovered → analysed → stored → published →
   written*. Each one names who chose the article and the AI's reason, and
   gives the lake's raw → processed → exploitation chain with record ids,
   code revision, models and threshold overrides. Each stage links to its
   own page.
4. **Reader** — the public view of the same article, its verdict and its
   sources, in Catalan, Spanish or English.
5. **Evaluation** — the numbers behind §2, with their intervals.

Trace is the strongest answer to "how do I know where this verdict came
from". It is also the demo of the data-architecture chapter (§4.3,
§5.5).

---

## 6. What changed in the interface on 3 Nov (for chapter 5.6)

- **`/trace`**: one article's journey from any id a page shows (URL, job,
  draft, story, reader id). Backed by `GET /trace`
  (`backend/src/services/trace.py`). It joins the selection rounds, the
  jobs (memory and journal), the lake's manifest (it opens no processed
  record), the reader index and the drafts on one key: the article's
  host and path.
- **Header quick jump**: "Trace a URL or id…", focused with `/`, on every
  operator page. It is absent on the public reader, because Trace is
  behind the password.
- **Cross-links between stages**: Analyze and Live job cards → Trace;
  Discover's queue → each pick's run on Live and its Trace; a draft → the
  analysed article, the published story and the Trace; Graph's related
  articles → Trace.
- **The Following dock**: every article sent from Discover or Analyze
  sits in the corner of every operator page, with its live stage (for
  example "Asking the model to judge the claim…"), then its outcome (on
  the reader with its verdict, withheld, rejected at admission, failed),
  and its Live and Trace links. Only running jobs are polled. It opens by
  itself when something new is sent.
- **Deep links**: `/live?job=<id>` opens and pins one run, falling back
  to the journal. `/?url=` and `/enrich?url=` prefill the URL and never
  start a run on their own.
- Tested: 9 backend tests (`tests/services/test_trace.py`, the API key
  included) and 7 e2e checks in headless Chrome (`scripts/e2e.py`), the
  dock's included.
