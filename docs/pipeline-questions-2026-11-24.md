# Questions to put to the pipeline — 24 November 2026

One question per decision the pipeline makes, in the order an article meets
them. The aim is to rethink each one, not to defend it: whether it is the right
decision, what it leaves out, and what else could be done. The committee's
questions about the thesis are in `docs/thesis-defense-brief.md`; this file is
about the pipeline itself.

Every "Now" line was read from the code on `dev` (d884294, with the
uncommitted work of 24 Nov) and from the decision records it names. Each
question has:

- **Now**: what the pipeline does today, with its file and default.
- **Could be missing**: why it might be a gap.
- **Other ways**: what else could be done.
- **Settle it**: the cheapest way to find out, often from data you already have.
- **Answer**: yours to fill in, as *keep (because...)*, *change*, or *a
  limitation to state in the thesis*.

## The pipeline as it runs today

```
discover    1-3 topic groups -> feeds and section pages -> mission screen -> rank
select      a person or the AI (titles and summaries) picks <= 20
fetch       extraction cascade (headless browser optional)
enrich      topics, sentiment, quality, keywords, claims, embedding (entities wait)
admit       topic, positive impact, duplicate                -> rejected: stored, no search
claims      2-4 anchor claims (centrality .5, subject .3, specificity .2)
            [restated as one checkable statement: on in the app, off in every benchmark]
search      3 queries (anchor, proposition, refutation), fused; SearXNG + internal corpus
evidence    8 pages fetched -> [temporal gate: benchmark only] -> copies out,
            one changed detail = FALSE -> rank (semantic .45, lexical .20,
            recency .20, reliability .15) + pertinence gate (.25) -> best 5
verify      one question per source (700 characters each); verdict = the side
            more outlets take, a tie UNVERIFIED
confidence  .7 verifier + .3 evidence; <= .6 with one outlet; <= .4 if ungrounded
            [second look: off]
article     worst claim wins -> publishable unless FALSE or MISLEADING
write       entities -> draft (closed world, [1] = the article) -> MiniCheck on
            the draft -> review -> rewrite -> publish
store       lake (the record) -> Neo4j (a view; the universe reads it)
```

---

## 0. Across the whole pipeline

### 0.1 Is the pipeline the app runs the one the thesis measured?

- **Now:** `backend/.env` sets `CLAIM_RESTATEMENT=standalone` (default `off`;
  the AVeriTeC protocol keeps it off) and `DUPLICATE_THRESHOLD=0.96` (default
  0.90). The harness enters at `FactChecker.check_claim`, so it skips admission,
  claim selection and the article's verdict. Its claims carry no figures
  (`Claim.facts` is empty), so its anchor query is weaker than the app's.
- **Could be missing:** every accuracy figure describes stages 3 to 6 under a
  configuration the app does not run. The restatement, which the app uses on
  every claim, has never been measured.
- **Other ways:** run the harness once with the app's own settings as a
  condition, or switch the restatement off in the app until it is measured.
- **Settle it:** run the brief's G13 experiment (train half, retrieval only,
  restatement on and off). Add a table to the thesis listing what differs
  between app and harness.
- **Answer:**

### 0.2 Is the job to find false claims, or to say how well a story is sourced?

- **Now:** the output is a five-way verdict per claim. The problem statement
  says constructive outlets rarely publish false claims; the custom set has
  0 natural FALSE, and its FALSE claims were made by changing a detail.
- **Could be missing:** the expensive part (search plus the 3B reading each
  source, ~45 s a claim) is tuned to find something that rarely happens here.
  What does happen gets only side figures: one press release repeated by many
  outlets, or one source only (`independent_domains`, confidence capped at 0.6).
- **Other ways:** make provenance the output. Who first said this? Is the
  primary source (the study, the report) reachable? How many independent
  outlets confirm it? Glockner et al. (2022): 73% of professional refutations
  go through the claimant's own source, not counter-evidence.
- **Settle it:** on every live analysis in the lake, count FALSE verdicts that
  a person would confirm, and UNVERIFIED verdicts caused by no independent
  source.
- **Answer:**

### 0.3 Where can a person step in on a claim?

- **Now:** a person acts at selection (picks up to 20) and at the draft
  (review, approve). Nothing asks a person about one claim's verdict. A claim in
  doubt becomes UNVERIFIED, and the article goes on (see 11.1).
- **Could be missing:** the thesis concludes the system is "a tool a journalist
  supervises", but on claims there is nowhere to supervise. The second look
  found 15 train claims "for a person" and was then switched off. The labeller,
  the one place a person judged claims, was removed on 17 Nov.
- **Other ways:** a queue of claims for a person: low confidence, outlets
  split, FALSE from one source, a withheld article. Store each answer as a
  label, so the gold set keeps growing instead of staying frozen.
- **Settle it:** from the lake, count how many claims per article would enter
  such a queue at a confidence of 0.5. If it is one or two, the queue is
  affordable.
- **Answer:**

---

## 1. Discovery

### 1.1 How much of the news worth finding does discovery find?

- **Now:** the configured sources' feeds and topic section pages, scoped to
  1-3 groups. Several feeds are dead or replaced (National Geographic and SINC
  404; CNN and WHO through a sitemap and an API; EFE and Reuters disabled).
  The Trending lens adds public signals.
- **Could be missing:** recall has never been measured, only counts (sources,
  links, candidates). Trends day 1 suggests a gap: all 12 stories worth
  offering were found by no topic round that day.
- **Other ways:** measure recall against what the outlet actually used. Then
  widen the sources, or search by topic, where recall is low.
- **Settle it:** the WordPress import keeps each post's source list
  (`source_list`, since 20 Nov). Over one month of posts, count how many of the
  editors' sources discovery would have listed. That is recall against real
  editorial choices, with no new labelling.
- **Answer:**

### 1.2 Is the mission screen's idea of "constructive" the editors' idea?

- **Now:** `selection/mission_screen.py` compares a story with written
  descriptions of positive impact and of off-mission kinds (party politics,
  crime, sport...). The descriptions were written by us.
- **Could be missing:** the descriptions were tested on one day of labels only.
  The outlet's 187 published posts are 187 examples of what the editors call
  constructive, and nothing has learned from them.
- **Other ways:** check the screen against the posts, or use them as examples
  (a classifier, or a few in the AI selection's prompt).
- **Settle it:** run the screen over the posts' source articles and see what
  share it would have dropped.
- **Answer:**

---

## 2. Selection

### 2.1 Should the AI choose from a title and a summary?

- **Now:** `selection/ai_selector.py` scores candidates from the feed's title
  and summary, one call at a time. The ranking weighs the story's reading and
  its group fit (split by `topicEmphasis`, 0.6), the source's record (0.25) and
  its reliability (0.15).
- **Could be missing:** a summary does not show whether the story has
  checkable claims and sources, and that decides whether it survives
  fact-checking. An article that will end UNVERIFIED costs as many minutes as
  one that will be published.
- **Other ways:** add checkability to the rank: does the summary name a
  study, a figure, an organisation? Or fetch the picks and run claim selection,
  which needs no model, before committing the analysis.
- **Settle it:** for the picks already analysed, compare selection rank with
  outcome (publishable, claims judged).
- **Answer:**

### 2.2 Does the system learn from what the editor chooses?

- **Now:** each round records who chose and how much of the AI's proposal was
  kept. Nothing reads it back. Laya was fine-tuned on selection labels and
  passed none of its rules.
- **Could be missing:** every round is a free label that goes unused.
- **Settle it:** count the rounds with a person's picks. From about ten
  rounds, refit the four ranking weights to them.
- **Answer:**

---

## 3. Extraction and enrichment

### 3.1 How often is an article's body incomplete, and would anyone notice?

- **Now:** the extraction cascade. Its last step, the headless browser, is
  usually absent locally and then reports `unavailable`, so the cascade keeps
  the previous step's answer. Bodies under 500 characters are refused.
- **Could be missing:** outcomes are counted per attempt, but the quality of
  what was kept never is. A truncated body yields fewer claims, a misleading
  lead, and a draft written from part of the story.
- **Settle it:** for 20 analysed articles, compare the stored body with the
  page by hand.
- **Answer:**

### 3.2 Which enrichment outputs decide anything?

- **Now:** topics, sentiment, quality, keywords, claims and an embedding; since
  17 Nov, entities only after the check. About 14 s for a 5,700-character
  article (16 Oct).
- **Could be missing:** `TopicPrediction.probability` carries no signal
  (known). Positive impact's minimum is 0.1 with its hard fail off (see 4.1).
  Some outputs may feed only the graph.
- **Settle it:** next to each output, write the decision it feeds. If it feeds
  none, mark it "for the graph" or drop it.
- **Answer:**

---

## 4. Admission

### 4.1 Is "positive impact" what the outlet means by constructive?

- **Now:** `admission/positive_impact.py` scores sentiment and quality only.
  The minimum is 0.1, and the hard fail is off by default. Selection's mission
  screen is a second definition, built on embeddings.
- **Could be missing:** two definitions that can disagree, and sentiment is not
  constructiveness. A solutions story about a disaster reads as negative.
  Constructive journalism (McIntyre 2017) is defined by solutions and context,
  not tone, which is what your five-part article already asks for.
- **Other ways:** one definition in both places; or a rubric (a problem, a
  response, evidence it works, its limits).
- **Settle it:** the WordPress import already ran admission on all 187 posts
  and recorded the decision. Read the share marked `not_positive_impact`: each
  one is a post the editors published that admission calls not constructive.
- **Answer:**

### 4.2 Should a duplicate be rejected, or merged?

- **Now:** a story too similar to a stored one is rejected (0.90; 0.96 in dev).
  An article is remembered only after its check.
- **Could be missing:** the same story from a second outlet is evidence, and
  may be the better-sourced version. Rejecting it loses both.
- **Other ways:** cluster the versions, keep the one with the most primary
  sources, and attach the others as sources.
- **Settle it:** count rejected duplicates, and check by hand how often the
  rejected one cited more.
- **Answer:**

---

## 5. Claims

### 5.1 Are 2-4 anchor claims enough, and what happens to the other sentences?

- **Now:** `ClaimSelector` keeps 2-4 claims, scored by centrality to the
  headline and lead (0.5), the article's subjects (0.3) and specificity (0.2).
  No other sentence is searched.
- **Could be missing:** the article is judged by 2-4 claims, but the draft is
  written from the whole article (source [1]). A figure in the sixth paragraph
  is never checked, yet can be published (see 12.1).
- **Other ways:** check every sentence with a figure, name or date cheaply
  (MiniCheck against the evidence already fetched), and keep the full verifier
  for the anchors. Or allow the writer to state as fact only what was checked.
- **Settle it:** in 10 drafts, count the sentences whose only source is [1]
  and whose fact is not an anchor claim.
- **Answer:**

### 5.2 Were the selection weights ever fitted?

- **Now:** 0.5 / 0.3 / 0.2, fixed in code. Precision is 0.64 over the
  labelling batches, most of which the AI labelled.
- **Could be missing:** the weights were reasoned, never fitted, and "the
  claims the article rests on" is measured as similarity to its headline.
- **Settle it:** the daily batches in `data/evaluation/queue/` record kept and
  skipped claims. Compare three weight sets offline; it needs no model.
- **Answer:**

### 5.3 Can the claim the app checks differ from the sentence the reader sees?

- **Now:** in the app, `restatement.py` asks the 3B to rewrite each claim as one
  checkable statement (for reported speech, the fact inside the quote). Rules
  without a model guard it: no invented number, no dropped figure, no question.
  An opinion with a speaker is judged as "they said it" (`opinion_claims:
  attribution`).
- **Could be missing:** a 3B writes what is then checked. A faithful-looking
  restatement can still shift the claim (scope, tense, who), and the rules
  catch figures, not meaning. It has not been measured.
- **Settle it:** read 20 restatements against their sentences by hand.
- **Answer:**

---

## 6. What is searched

### 6.1 Are three queries planned from the sentence the right search?

- **Now:** `query_builder.py` plans anchor, proposition and refutation queries,
  fused by reciprocal rank, in one round. `query_plan: checkable` and
  `questions` are built and off. The second look is off.
- **Could be missing:** nothing asks what kind of source would settle the
  claim, which is what `/what-to-search` makes Claude do first. The primary
  source (the study, the official statistic, the organisation's own page) is
  found only by chance.
- **Other ways:** split the claim into questions (the AVeriTeC baseline,
  InFact, HerO); add a query aimed at the primary source; or let a stronger
  model plan a second round.
- **Settle it:** in the troubleshooting batches and `searches-train10.jsonl`,
  count how often the decisive source was a primary source the three queries
  missed.
- **Answer:**

### 6.2 Can the pipeline rely on free engines through SearXNG?

- **Now:** the engines changed on 3 Nov and on 23 Nov. Yandex and PrivacyWall
  are in; Google, Yep, Brave, Startpage and Mojeek are out, because they refuse
  this machine. A failed search is `searchUnavailable`, and an off-subject
  answer counts as a failed search.
- **Could be missing:** quality depends on which free engine tolerates this IP
  this week. A cloud VM's IP, where production would run, has never been tried.
- **Other ways:** a keyed search API in production (the thesis's future work,
  §9.4.1); a search cache; refuse to start analyses while search is failing,
  rather than publish "Not checked" (see 11.1).
- **Settle it:** read the source-health panel daily for a week, and measure once
  from a cloud IP.
- **Answer:**

### 6.3 Can the internal corpus corroborate a story with itself?

- **Now:** `vector_retriever.py` searches previously analysed articles in Qdrant
  beside the web. The article's own copy is excluded, and word-for-word copies
  are removed by `independence.py`.
- **Could be missing:** a stored article written from the same press release,
  but paraphrased, passes both filters and counts as a second outlet.
- **Settle it:** count how often an internal hit is cited, and whether it shares
  the claim's original source.
- **Answer:**

---

## 7. Which evidence counts

### 7.1 Why does recency weigh 0.20?

- **Now:** ranking weighs semantic 0.45, lexical 0.20, recency 0.20 and
  reliability 0.15 (environment-only). Recency decays from today, or from the
  claim's date under the benchmark's cutoff. Newer scores higher.
- **Could be missing:** the source that settles a claim is often older than its
  coverage (the 2022 study, last year's report). Recency favours later
  coverage, which is mostly retelling.
- **Other ways:** recency only for claims about something that changes; or
  favour the earliest source.
- **Settle it:** re-rank one run's stored evidence with recency at 0 and replay
  the verifier on it.
- **Answer:**

### 7.2 Should reliability decide the verdict, not only the ranking?

- **Now:** 65 source YAMLs carry a rating; any other domain gets 0.5 and
  `reliability_known: false`. Reliability is 0.15 of the ranking. In the
  verdict, `per_source.verdict_from` counts outlets equally: an unrated blog
  weighs the same as a health ministry.
- **Could be missing:** the verdict ignores who is speaking. How the 65 were
  rated, and by whom, is also a question you will be asked.
- **Other ways:** a vote weighted by reliability; require at least one rated
  source for TRUE; or show which kind of source each side has.
- **Settle it:** on a replayed run, count the verdicts a weighted vote would
  flip.
- **Answer:**

### 7.3 Does removing copies leave a new story with no evidence at all?

- **Now:** `independence.py` drops a page that repeats the claim's sentence word
  for word. A page with the same sentence and one detail changed makes the claim
  FALSE without the model, unless a copy also exists.
- **Could be missing:** for a story a few days old, the press release and its
  copies may be all there is, so an honest UNVERIFIED becomes the usual
  outcome. In the app there is no date cutoff, so a later update of a figure (a
  revised count, a corrected date) reads as "one changed detail". That makes a
  correct article FALSE and withholds it.
- **Settle it:** in live runs, count how often each rule fired, and read every
  FALSE that came from a changed detail.
- **Answer:**

### 7.4 Is 700 characters a source enough to judge?

- **Now:** `verifier_excerpt: passages`: the 700 characters of each page most
  about the claim, for the best 5 of 8 fetched pages.
- **Could be missing:** "silent" is the most common stance, and the 3B answered
  FALSE "for want of a detail". Was the detail in the page, outside the
  excerpt?
- **Settle it:** for 20 "silent" answers, read the whole page.
- **Answer:**

---

## 8. Verification

### 8.1 Is "the side more outlets take" the right rule?

- **Now:** one question per source; more outlets supporting gives TRUE, more
  contradicting gives FALSE, and a tie or none gives UNVERIFIED. The
  confidence grows with the agreeing share.
- **Could be missing:** one authoritative contradiction (the official
  statistic) is outvoted by two retellings. The module's own docstring says the
  3B answers "contradicts" to a true claim about as often as "supports" to a
  false one, so the vote averages noise rather than removing it.
- **Other ways:** MiniCheck for support and the chat model only for
  contradiction, as `evaluation.md` proposes; a reliability-weighted vote
  (7.2); a stronger reader (8.3).
- **Settle it:** the 40-claim balanced AVeriTeC comparison
  (`experiments/verifier/averitec-balanced.md`), done on 24 Nov. The 3B under
  this rule got 10 of 40, the same as always answering Refuted, and gpt-oss-120b
  got 18 under the same rule. The rule is not what holds the 3B back: its reading
  of each source is.
- **Answer:**

### 8.2 Can the verifier say every verdict the reader explains?

- **Now:** `Verdict` has five values, and the reader's guide explains all five.
  The per-source verifier never answers PARTIALLY_TRUE or MISLEADING
  (28 Oct audit). MiniCheck answers only TRUE or UNVERIFIED. FALSE comes from
  the vote or from a changed detail.
- **Could be missing:** MISLEADING blocks publication, but the default pipeline
  cannot produce it. The label set promises more than the verifier can say.
- **Other ways:** cut the set to what the verifier can say (TRUE, FALSE,
  UNVERIFIED, plus "outlets disagree"), or give MISLEADING a rule of its own
  (the claim is true, and the article's framing overstates it).
- **Settle it:** count verdicts in the lake since 22 Oct, by label.
- **Answer:**

### 8.3 Is a confidently wrong verdict worse than an honest UNVERIFIED, and by how much?

- **Now:** `llama3.2:3b`, about 45 s of model time a claim on this CPU. On the
  annotator's pages the 9B was as accurate but right on 72.9% of the verdicts it
  committed to, against 55.6% (+17.4 [+2.7, +32.0]), at three times the time.
  On Groq, gpt-oss-120b takes 3.1 s a claim, about $0.064 per 100 claims.
- **Could be missing:** the roadmap leaves "whether a wrong verdict costs more
  than an honest UNVERIFIED" as the author's call (19 Oct), and it has not been
  made. The choice of model depends on it.
- **Settle it:** write down the ratio (say, one confidently wrong verdict costs
  as much as three UNVERIFIED) and pick the model by it, from figures you
  already have.
- **Answer:**

---

## 9. Confidence

### 9.1 Does a confidence of 0.8 mean right 80% of the time?

- **Now:** 0.7 × the verifier's figure plus 0.3 × the evidence's quality, at
  most 0.6 with one outlet and at most 0.4 when ungrounded
  (`confidence_scorer.py`). The reader shows it, and its guide explains it.
- **Could be missing:** it has never been calibrated. No report draws a
  reliability curve, although the thesis cites Guo et al. (2017). Readers are
  shown a number with no measured meaning.
- **Other ways:** calibrate it; show bands (low, medium, high) instead of a
  number; or show what produced it ("2 of 3 outlets state it").
- **Settle it:** from the harness records you already have (custom test half,
  AVeriTeC), bin confidence against accuracy. No new run.
- **Answer:**

---

## 10. The second look

### 10.1 Was the idea wrong, or only its query writer?

- **Now:** off. On train its trigger gained +2.9 [-2.9, +8.7]; on test, 0. The
  3B writes the follow-up queries from its first explanation.
- **Could be missing:** it is the pipeline's only second round of search. A
  weak query writer may have sunk it, not the idea.
- **Other ways:** the same trigger, with a stronger model or the
  `/what-to-search` approach writing the queries; or send its claims to a
  person instead (0.3).
- **Settle it:** read the 15 claims it marked "for a person": would a second
  search have settled them?
- **Answer:**

---

## 11. The article's verdict and the decision to publish

### 11.1 Should "not refuted" be enough to publish?

- **Now:** `DataLakeRepository.is_publishable` requires the article to pass
  admission and its worst verdict to be neither FALSE nor MISLEADING. **An
  article whose claims are all UNVERIFIED, or whose search failed for every
  claim, is publishable.** The reader then shows UNVERIFIED or Not checked.
  Entities and drafts follow the same rule.
- **Could be missing:** the method chapter says the pipeline fails closed
  (§4.6). That holds for each claim's verdict, but the publication gate fails
  open: a search outage yields articles on the reader, and drafts written from
  them.
- **Other ways:** require at least one claim judged TRUE (`foundVerdict`), or
  some number of claims judged; never publish an article where no claim was
  checked; or keep the rule and say plainly that publication means "nothing
  was found false".
- **Settle it:** count the publishable articles in the lake where
  `claimsJudged` is 0.
- **Answer:**

### 11.2 Should one verifier error withhold an article?

- **Now:** the article takes its worst claim's verdict (TRUE < PARTIALLY_TRUE <
  UNVERIFIED < MISLEADING < FALSE), with `foundVerdict` and the claim counts
  reported beside it. One FALSE withholds the article.
- **Could be missing:** in the HPV article, the 3B marked two sources quoting
  the claim word for word as contradicting it, and the article was withheld. No
  one is told when an article is withheld, and a FALSE on a side detail weighs
  the same as one on the headline claim.
- **Other ways:** a FALSE goes to a person instead of withholding (0.3);
  weight by the claim's centrality, which the selector already computes.
- **Settle it:** list every withheld article and read why.
- **Answer:**

### 11.3 Should the readers' universe show what the reader view withholds?

- **Now:** since 23 Nov the universe reads every article of the positive graph
  (`MAP_SOURCE=graph`), each with the verdict the graph recorded. Of the 12 the
  pipeline analysed, 6 show FALSE, from a 3B that answers FALSE to true claims
  (`docs/decisions/news-map.md`). The reader view publishes none of them.
- **Could be missing:** two ways for readers to see the stories, under two
  publication rules. A news outlet showing other outlets' stories marked FALSE
  by a model is a reputational and possibly legal exposure. Check whether the
  universe says anywhere that the verdict is a model's.
- **Other ways:** the universe shows only what is publishable, plus the
  imported posts; or a FALSE is shown only behind the password.
- **Settle it:** decide who can open the universe, and apply the reader view's
  rule there.
- **Answer:**

---

## 12. The draft, its check and publishing

### 12.1 What does the second check actually check?

- **Now:** `draft_fact_check.py` scores each cited sentence of the draft with
  MiniCheck against the excerpts of the sources it cites. Source [1] is the
  analysed article itself. A sentence below 0.5 is listed, not removed.
  Approval needs the check to have run, not to have passed.
- **Could be missing:** a sentence citing [1] passes because the article says
  it. The second check tests whether the draft is faithful to its sources, not
  whether it is true. Combined with 5.1, a fact that was never searched can be
  published under "checked twice", and unsupported sentences do not stop
  approval.
- **Other ways:** treat a sentence resting on [1] alone as unchecked, unless
  it matches a verified anchor claim. Block approval while a sentence is
  unsupported, or make a person tick each one.
- **Settle it:** in 10 drafts, count the sentences citing only [1], and the
  unsupported sentences at approval.
- **Answer:**

### 12.2 Is MiniCheck's 0.5 right for these drafts?

- **Now:** the authors' threshold, untuned here. MiniCheck was trained on
  English; Spanish is translated by OPUS-MT first. On the custom set's Spanish
  claims, translation brought no detectable gain.
- **Could be missing:** no draft sentence has been scored by a person, so how
  often the check is wrong on drafts is unknown.
- **Settle it:** score 30 draft sentences by hand (supported or not) and
  compare with MiniCheck at 0.5.
- **Answer:**

### 12.3 Is the writer measured?

- **Now:** writer `qwen3.5:4b` and reviewer `qwen3.5:9b`, chosen on a few
  seeded texts. The writing benchmark stands at 1/36 and 15/36. Out of the
  thesis's scope, but it writes what readers read.
- **Settle it:** if any part of writing enters the thesis, make it 12.1's
  counts, which need no benchmark.
- **Answer:**

---

## 13. Storage

### 13.1 Is the lake still the record, if readers read the graph?

- **Now:** the lake is the record and Neo4j a view that sync rebuilds
  (`docs/decisions/graph.md`). Since 23 Nov the universe reads the graph. A
  claim node is shared by every article with the same sentence.
- **Could be missing:** what readers see now comes from the view, not the
  record. A shared claim node can carry another article's verdict and pages
  (the map already leaves evidence out for that reason).
- **Settle it:** check `./scripts/check.sh lake` passes, then compare each graph
  article's verdict with its exploitation record's verdict.
- **Answer:**

---

## 14. Measuring the pipeline

### 14.1 Which stages have a number, and does any number cover the whole?

| Stage | Measured | Where |
|---|---|---|
| Discovery | counts only; trends day 1, labelled by Claude | `experiments/discovery/`, `trends/` |
| Selection | AI against the editor: not run | — |
| Extraction | attempt outcomes, not body quality | `/scraper` |
| Admission | topic group right 0.73 [0.59, 0.85]; positive impact: none | `experiments/topics/` |
| Claim selection | precision 0.64, AI-labelled batches | `queue/` |
| Retrieval | against the annotator's pages, -2.9 [-17.1, +11.4] | `evaluation.md` |
| Verification | custom test 51-56%; AVeriTeC balanced, 10 claims | reports |
| Confidence | not calibrated | — |
| Article verdict and publication | not measured | — |
| Draft check | not measured on drafts | — |

- **Could be missing:** no figure covers the whole pipeline: of the articles it
  published, how many would an editor publish?
- **Settle it:** `POST /imports/wordpress?verify=true` runs the full check on
  posts the editors already published. The share it withholds, and why, is an
  end-to-end figure against real editorial decisions (positives only, so it
  measures false alarms, not misses).
- **Answer:**

---

## The gaps to look at first

1. **What gets published (11.1, 11.3, 12.1).** The publication gate passes
   articles where nothing was checked. The universe shows FALSE verdicts the
   reader view withholds. The second check passes facts that were never
   searched. These are about what readers see, not accuracy, so they come first.
2. **The configuration the app runs is not the one measured (0.1).**
3. **A number shown to readers without a measured meaning (9.1).**
4. **The verdict rule (7.2, 8.1, 8.2).** It ignores who is speaking, and two of
   its five labels are unreachable by default.
5. **No place for a person on a claim (0.3, 11.2).** That is the
   supervision the thesis's conclusion rests on.

**Settled from data you already have, with no new run:** 1.1 (the import's
source lists), 4.1 (admission's decisions on the import), 8.2 (verdicts by
label in the lake), 9.1 (confidence against accuracy in the reports), 11.1
(publishable articles with no claim judged), 11.2 (the withheld articles).
