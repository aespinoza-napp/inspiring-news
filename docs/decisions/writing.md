# Writing: from an analysed article to a published one

**Started 2026-10-15**, on `feature/newsroom-writing`. Out of the Oct 14
feature freeze by the author's decision: the roadmap had writing at P2
("Writing from verified sources", P1.3's design), behind every P0 and P1
item.

The newsroom's last steps. After an article has been analysed, a person
asks for a new article on the same story: the system finds news related
to it, writes a draft from those sources and the fact-checks, in
Catalan, Spanish or English, following the person's indications. The
corrector reviews it; if the metrics fall short, the person can have it
rewritten; once satisfied, they publish it. Today only to the web - this
app's own public reader. TikTok and Instagram are channels with nothing
behind them yet.

```
analysed article ──> write (related news + fact-checks + indications)
                          │
                          v
                     draft ──> review (corrector metrics, proposed corrections)
                       ^            │
                       │   below target? ──> rewrite (guided by the failing metrics)
                       │            │
                       └── edit ────┘
                                    │ satisfied
                                    v
                              approve ──> publish (web; TikTok, Instagram later)
```

## The contract

Built first, so the stages could be built at once. Each stage fills its
own fields and leaves the others alone.

- **One shape:** `ArticleDraft` (`backend/src/models/writer/draft.py`),
  mirrored in `frontend/src/lib/drafts.ts`. snake_case in Python,
  camelCase on disk and over the API (`by_alias=True`).
- **One store:** `DraftStore` (`backend/src/services/writer/draft_store.py`),
  one JSON file per draft under `settings.DRAFTS_PATH` (beside the lake,
  not in it). Every change is `update(id, change)`, a read-modify-write
  under one lock. `revise()` replaces the content and keeps history: the
  outgoing revision keeps its review, the draft's `review` is cleared.
- **Background work:** `run_in_background(id, busy, work)` marks the
  draft `busy`, runs `work` on a thread, keeps a failure in `error`,
  clears `busy`. A second step on a busy draft is a 409. A restart
  clears a stale `busy` with "Interrupted". Tests pass `wait=True`.
- **Citations:** the body cites `[n]`, 1-based into `sources`, which is
  never reordered once the draft exists.
- **Status** is editorial: `draft` → `approved` → `published`. What is
  running is `busy`. A person's edit sends an approved draft back to
  `draft`, and is refused on a published one.
- **Routes:** one module per stage, registered in `main.py` -
  `draft_routes.py` (list, get, edit; the writer adds create),
  `review_routes.py`, `publish_routes.py`; the rewrite stage adds its own.
  Everything under `/drafts` takes the API key.
- **Frontend:** one proxy, `app/api/drafts/[[...path]]/route.ts`, with
  every stage's action already allowlisted (`review`,
  `accept-correction`, `rewrite`, `approve`, `publish`, `unpublish`,
  `content`). `/drafts` lists and starts drafts; `/drafts/[id]` polls
  while `busy` and renders one component per stage, each taking
  `DraftStageProps` (`components/drafts/`).
- **One body renderer:** `components/drafts/ArticleBody.tsx`, for the
  draft and the public page alike. React elements, never HTML (the text
  is a model's and the public sees it); `[n]` links to `#source-n`, the
  id every source list gives its n-th source.
- **Settings:** `DRAFTS_PATH`, `WRITER_LLM_MODEL` and
  `CORRECTOR_LLM_MODEL` (None = `LLM_MODEL`), `WRITER_LLM_TIMEOUT`
  (300 s). Infrastructure, in `NON_THRESHOLD_SETTINGS`. Targets a run
  can tune go in `PipelineThresholds`.
- **Tests:** `create_draft()` in `tests/factories.py`; the `draft_store`
  fixture puts a store over `tmp_path` in the container.

`/drafts` is behind the site password; only `/reader/*` is public
(Caddy's `@reader`). So nothing that starts a draft can live on the
reader's pages.

## Writing

*To be filled by the writer stage.*

## Review

**Built 2026-10-15.** `POST /drafts/{id}/review` (`src/api/review_routes.py`)
runs `DraftReviewer.review` (`src/services/corrector/draft_reviewer.py`) in
the background and saves a `DraftReview` on `draft.review`;
`POST /drafts/{id}/accept-correction` makes its proposal the content. The
page's `components/drafts/DraftReviewPanel.tsx` starts one, shows it and
offers the proposal.

**Nine metrics**, each a `CorrectionMetric`, 0-100, higher is better -
hallucinationIndex included, as on `/correct`:

- **title** and **subtitle**, which free text does not have: clarity,
  accuracy to the body, length, and how each works as a headline and a
  standfirst on the web. The model judges them; lengths are also checked
  without it (a title over 70 characters or under 20, a subtitle over 200,
  a citation marker in either). A missing subtitle caps its score at 20.
- the corrector's seven. **readability** and **coverageVerification** are
  deterministic as on `/correct`, but in the draft's *declared* language,
  never detected. readability also lists the three longest sentences past
  35 words. coverageVerification is the admission filter's
  positive-impact score: how the draft fits Inspiring's mission.
  **grammar, factConsistency, seo, hallucinationIndex, style** come from
  the model.

**Grounded in what the writer was given.** Free text has nothing to be
held to; a draft has `sources[].excerpt` (the only text of each source the
writer saw) and `fact_checks` with the pipeline's verdicts. The model is
given both and asked to check every factual sentence against the source
it cites. Then `grounding.py` checks, without the model, what a small
model reading a long prompt misses:

| Check | Reported under | Binds the score? |
|---|---|---|
| A factual sentence with no `[n]` | hallucinationIndex | Yes: capped at the share of factual sentences that cite something |
| `[n]` with no n-th source | factConsistency | Yes: 20 off the ceiling for each |
| A sentence repeating a claim judged FALSE or MISLEADING | factConsistency | No |
| ... judged UNVERIFIED | hallucinationIndex | No |

"Factual" is a heuristic: a figure, a month, or a named subject with a
reporting verb ("the University of Girona found", "Barcelona va
anunciar") from the language's lexicon. A reporting verb alone is not
enough - the lexicons' verb prefixes are built for recall ("public*" is
also "público") - and units are left out ("people" is a unit there). The
repeated-claim check is word overlap with the claim, so it only works when
the draft is in the analysed article's language, and it cannot tell
asserting a claim from refuting it: reported for a person, never scored.
A cap says so in the summary ("Capped at 50: 1 of 2 factual sentences
cite no source."). An unavailable metric keeps its 0 and
`UNAVAILABLE_SUMMARY`, and still gets the checks' issues.

**Two model calls, review then correction.** The correction is handed the
review's issues, as an editor's notes go to the copy desk; each prompt
asks one thing of a small local model, which loses the thread of nine
scores and a rewritten article in one JSON object and truncates long
strings inside it; a correction that fails leaves the metrics; and the
correction is not given the excerpts (it may add no facts), so its prompt
is shorter. `TextCorrector.llm_metrics` and its `SYSTEM_PROMPT` are
untouched: the writing benchmark measures exactly that prompt
(`src/evaluation/writing.py`). The draft review is a different instrument;
both read a model's answer with the same `normalize_metric`.

**The proposal** (`corrected`) fixes grammar, style, SEO, readability,
title and subtitle, adds no facts, keeps every `[n]` with its statement
and keeps the draft's language. It may soften or remove a sentence the
review found unsupported, never add support. It is checked before a
person is offered it - accepting replaces the article - and dropped
(`corrected: null`, logged) when it:

- cites a source the draft never cited, or no longer cites one it did;
- is under half or over 1.8 times the body's length (cut off, or padded);
- came back in another language: its share of the language's stopwords
  fell below half the draft's. Catalan's stopwords are only words Spanish
  does not use, so a Spanish translation of a Catalan draft scores 0 on
  them;
- carries a figure (a run of digits) that is nowhere in the draft;
- cites `[n]` on a sentence that shares under a quarter of its content
  stems with every sentence of the draft that cited `[n]` - the citation
  moved onto a statement its source was never cited for.

The last two came from the live run below. A number written out in words
("ten" for "10") is not caught; a figure merely reformatted ("1,200" for
"1200") is refused, which is the safe side.

**Accepting** is synchronous: `revise(draft, review.corrected,
"corrected", review.model)` - the outgoing revision keeps the review of
its own text, the draft's is cleared - and an approved draft goes back to
`draft`, as after a person's edit. 409 while busy, once published, and
with no proposal.

**A review never describes text it did not read.** The route snapshots the
content before reviewing and attaches the review only if the draft's
content is still that; otherwise the draft's `error` says it changed and
asks for another review. Edits are refused while a draft is busy, so this
is the guard for whatever else changes a draft meanwhile, not the common
path.

**Failures.** The model unreachable for the review, or `inference/` down
(sentiment, for coverage), fails the review into `error`, rather than
saving a review of zeros the rewrite loop would read as failing metrics.
Coverage is computed before the model is asked, so a dead `inference/`
costs no model time.
A model that answers with something unusable is a review:
`UNAVAILABLE_SUMMARY` on its metrics, `corrected: null`. Unreachable for
the correction alone: the metrics stand, `corrected: null`.

**Model.** `LLMClient(model=CORRECTOR_LLM_MODEL or LLM_MODEL,
timeout=WRITER_LLM_TIMEOUT)` (`container.get_draft_reviewer`): a draft
need not be judged by the model that wrote it, and a whole article with
its sources overruns `LLM_TIMEOUT`'s 30 s. It shares `/correct`'s
sentiment and quality analysers.

### Catalan

A draft can be `ca`; no source is. Three things were checked before
choosing:

- **The lexicon.** `lexicon_for` falls back to English for anything but
  `en`/`es`, and `LanguageDetector` tells apart exactly what is in
  `LEXICONS`. So Catalan has a **complete** lexicon (`CATALAN`, every
  field, held to the same completeness test as English and Spanish in
  `tests/test_invariants.py`), but in `WRITING_LEXICONS`, not `LEXICONS`:
  adding it there would change how every ingested Spanish article is
  detected and scored, for a corrector metric. The review asks
  `writing_lexicon_for`, which raises for an unknown language instead of
  falling back. `QualityAnalyzer`'s metrics are called one by one with the
  lexicon object, because `process(language="ca")` resolves the code with
  `lexicon_for`. Catalan text is prepared for the word lists: `l·l` folded
  to `ll` (`·` is not a word character, so "col·laboració" split in two)
  and elided articles split off ("d'investigació" was one token).
- **Readability.** textstat has no Catalan formula, and asked for "ca" its
  Flesch reading ease silently uses the **English** constants over Catalan
  syllables (a plain two-sentence Catalan text: 61, against 100 with the
  Spanish formula). No reading-ease formula validated for Catalan was found
  to cite. So Catalan is measured with a **named stand-in**:
  Fernández-Huerta (Fernández Huerta, J. (1959). Medidas sencillas de
  lecturabilidad. *Consigna*, 214, 29-32), fitted to Spanish, over Catalan
  syllable counts (Pyphen's Catalan dictionary). Every Catalan review's
  readability summary begins "Stand-in for Catalan" and says it is
  indicative, not calibrated.
- **Sentiment**, a part of coverage, comes from `inference/`'s
  `cardiffnlp/twitter-xlm-roberta-base-sentiment`: XLM-R, fine-tuned on
  eight languages, Catalan not among them. Its Catalan reading rests on
  multilingual pretraining, and the coverage summary of a Catalan draft
  says so.

### Live

2026-10-15, `llama3.2:3b` on the local Ollama - the only model pulled.
Docker was down, so `inference/` was too: sentiment was a fixed neutral
stand-in and coverageVerification was not live; everything the model did
was. Two hand-written drafts, English and Catalan, seeded with defects:
"it's" for "its" (en) and "esta" for "està" (ca), 3 million euros where
the source says 1.2 (en), a sentence stating as fact the claim the
fact-checks judged FALSE ("the bay is now completely free of plastic
pollution", uncited), and in English an 8-character title with no
subtitle.

- **The review** took 27 s (en) and 11 s (ca); every metric parsed.
- **Caught**: the FALSE claim, by the model in both drafts and by the
  overlap check in English (the claim is English, so in the Catalan draft
  only the model could). The title's length and the missing subtitle were
  the code's checks.
- **Missed** by the model: both spelling errors (grammar 100 in both), the
  wrong figure (3 million against the source's 1.2). It said the Catalan
  draft's meadow area was in no source (it is, in [1]), and gave the
  English draft hallucinationIndex **0** with a summary saying it cites
  accurately - the inverted scale the prompt warns against.
- **The proposals.** English: Ollama aborted the correction twice ("token
  repeat limit reached", which the client reports as unreachable), so no
  proposal; the metrics stood. Catalan: it turned "deu anys" into "6
  anys", dropped `[2]`, moved `[1]` onto the plastics sentence, merged the
  paragraphs and dropped the subheading - and **passed every check that
  existed then**. Hence the figure, dropped-source and moved-citation
  rules; that proposal is now a test
  (`test_the_first_live_catalan_proposal_is_not_offered`), and each rule
  catches it alone.

Read: a 3B model is not enough to correct an article. It reads the
verdicts but not the excerpts, and its proposal changes facts. Set
`CORRECTOR_LLM_MODEL` to a larger model once one is pulled (none was:
the brief allowed no pulls) and run the writing benchmark on it. Until
then the deterministic checks are what holds, and no proposal reaches
the article without a person accepting it.

### Gaps in the contract

- `DraftReview` has nowhere to say **why** `corrected` is null - an
  unusable answer, a rule broken, the model unreachable. It is logged;
  the panel lists the possibilities.
- `CorrectionMetric` has no "not scored" flag; `UNAVAILABLE_SUMMARY` is the
  marker, as on `/correct`, and the panel matches its first words. A
  rewrite loop reading the metrics needs to skip those, not read them
  as 0.
- No per-run targets for the metrics yet: "below target" belongs to the
  rewrite stage, in `PipelineThresholds`.
- No endpoint creates a draft yet (the writer's), so the live run wrote
  its drafts into a scratch `DraftStore` directly.

## Rewriting

*To be filled by the rewrite stage.*

## Publishing

*To be filled by the publishing stage.*
