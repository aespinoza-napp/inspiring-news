# Trends: what goes viral, and the good news in it

Asked for on 2026-10-26 by the author: a way for the scraper to find
TikTok trends and other viral things, as a new topic, and to draw a good
story or a positive angle from them. Planned the same morning (the
roadmap artifact's "Trends" section), added to the plan as 76 hours on
top of the 900, free tools only, and built on `feature/trends`. The
goals are in `docs/goals.md`, "Trends".

The idea in one line: **a trend is a question - why is everyone talking
about this? - and the answer is in the news that explains it.** The
pipeline never analyses a trend. It reads *signals* of what is spreading,
finds the articles that explain each one, and sends those through the
same screen, ranking, choice and fact-check as every other candidate;
the trend travels with them as a card. **Virality decides what gets
looked at, never what is believed**: it never enters a verdict, a
confidence or a source's rating.

## What the morning of 26 Oct showed

Read by hand at 07:10, before anything was built:

- Spain's ten rising searches: a TV talent show, a bullfighter's noisy
  birthday party, two tennis matches and a basketball player, a lorry
  overturned on the AP-7, Moroccan warships off Ceuta, a television
  presenter, Madrid's Metro line 10 reopening, and Ester Expósito in
  Netflix's *La Regenta*. The US ten: children's savings accounts
  (twice), Walmart's stock, a crash, a winter forecast, a football
  player, wrestling, the war in Ukraine, a TV series, a cloud stock.
  **None good news in itself**; two of Spain's with an angle sources
  could support (a metro line back in service; a classic finding new
  readers, if sales or loans say so). The tennis trends came with two
  betting sites' odds pages.
- r/UpliftingNews' front page linked 24 articles from 20 domains, about
  20 of them positive (a liquid that stopped tooth decay, a PTSD trial, a
  toad declared extinct in 1989 found again) - and an election result and
  a police story. About half were about private people, some of them
  children.

What is viral and what is good news barely overlap, so the lens takes
two inputs: *trend first* (what is spreading, and is there a good story
in it?) and *positive first* (good news that is already spreading).

## TikTok is not read, and why

- Its Creative Center now redirects to "TikTok One Creative Suite", a
  page built in the browser. Its listing endpoint answered
  `{"code":40101,"msg":"no permission"}` without a signed-in session, and
  TikTok's terms forbid scraping.
- The Research API is by application, for researchers at not-for-profit
  institutions; the EU's DSA Article 40 portal opened on 28 Oct 2025, and
  one published request for TikTok data was refused in February 2026.
  Neither arrives before 31 Dec.
- Paid scrapers (Apify, RapidAPI) cost money and break the same terms:
  out twice.

So TikTok reaches the system as its echo - the searches and the news a
trend causes - and as a hashtag or a link a person types. A link is kept
as the trend's video, which a published story can show through TikTok's
own player (oEmbed: public, no key). oEmbed answered `ratelimit
triggered` after a few requests on 26 Oct, so nothing depends on it.

## The signals (built 2026-10-26, T1)

A **signal** is a public feed that says what is spreading. Not a news
source: a source is read for its articles and rated, by domain, one
source per domain; a signal is never evidence, and Google Trends is one
domain (`trends.google.com`) for every country. So signals have their own
folder, `backend/data/trends/`, and model, `TrendSignal`
(`src/models/core/trend_signal.py`), loaded by `TrendSignalRepository`.

| Signal | Kind | What a trend is | Its articles |
|---|---|---|---|
| `google_trends_es`, `google_trends_us` | `google_trends` | A rising search, with approximate searches (`500+` -> 500) and the time it started | The three news items Google attaches |
| `uplifting_news` (r/UpliftingNews, top of the day) | `ranked_feed`, `positive` | A post, its place in the day's votes | The article it was submitted with; never the thread. A self-post, an image or a video on Reddit is skipped |
| `upworthy` | `ranked_feed`, `positive` | An item, newest first | The item itself, with its time and snippet |
| `know_your_meme` | `ranked_feed` | An item | The explainer itself |

Mexico and the UK answer Google's feed too; they are one YAML away.
Every signal's language has a lexicon (`TrendSignal` refuses another,
as invariant 8 does for sources). `positive` marks a signal whose items
were chosen for being good news; it exempts nothing from the screen,
since r/UpliftingNews also carried politics.

**Reading** (`src/services/trends/`, no `__init__.py`):

- `readers.py`: pure functions over a feed's text, tested on the feeds
  saved on 26 Oct (`backend/tests/fixtures/trends/`). Google's RSS is
  parsed with ElementTree, not feedparser, which keeps only the last of a
  repeated `ht:news_item`; expat 2.6.4 refuses entity-expansion attacks.
  An HTML error page parses in feedparser as an empty feed with no
  version, and is refused as `FeedError`.
- `trend_service.py`: `TrendService.read(signal_ids)` reads the signals at
  once (`bounded_map`, four at a time, in order) through the shared
  `Fetcher` - URL guard, timeout, redirects hop by hop - and counts each
  read on `/scraper` under the purpose `trends`. A signal that fails is
  reported with why, never raised.
- `seeds.py`, `TrendService.seed(text)`: a person's line. Its hashtags, as
  words (`#FarmearAura` -> "Farmear Aura"; reach tags like `#fyp`
  dropped), or its words, name the trend. A TikTok link becomes its video:
  the id from the link, the caption and author from oEmbed when it
  answers, and the caption names the trend when nothing else does. Any
  other link is the trend's first article. A seed with nothing to search
  for is refused.
- `TrendService.search_articles(trends, per_trend)`: a news search of a
  trend's name (`!news <name>` in its language) through the fact-check's
  `SearxngClient`, DuckDuckGo behind it. New pages only (host and path
  compared), after the signal's own. A search that cannot be answered
  leaves a note and the signal's articles. Off by default for signals,
  which bring their own articles; on for seeds.
- `trends.py`: `Trend` and `TrendArticle`. A trend's id is a hash of its
  signal and its folded name, so the same search read an hour later is
  the same trend. `card()` is what a candidate carries.

Reddit limits readers without a key: a second request minutes after the
first came back empty on 26 Oct. The signal then reports no trends and
the round goes on without it.

## The lens (built 2026-10-26, T2)

**Trending is a way into `/discover`, not a sixth group.** The person
sees a new button beside the five groups. Underneath it is a lens:
virality is how a story travels and says nothing about what it is about.
A viral koala rescue is still Nature, and the classifier keeps saying
so. As a group it would have fought the code three ways: `GROUP_FIT`
would list the best viral stories last as "of another group", the
labeller's copy of the groups and the evaluation's balance over five
would change under 139 labelled facts, and every source would need a yes
or no for trends.

`POST /ingest/rounds {trending: true, signals?, seed?, search?, groups?,
perSource, topicEmphasis?}` (`src/services/trends/trending.py`,
`TrendingDiscovery`, through `SelectionService.create_round`). Groups
are optional and do not count towards the three; when given, they order
what fits them first at the round's topic emphasis, as in a topic round.
`signals`, `seed` and `search` are refused on a topic round. Unknown
signals, more than five articles a trend, a seed over 300 characters,
and a round with no signal and no seed are refused before anything is
read.

What an article must pass, in order:

1. **A page that looks like an article** (the feed step's own rule), not
   in an off-mission section or a live page, and **not a betting site**:
   `BETTING_DOMAINS` (`src/config/topic_url_patterns.py`), matched on the
   host and its parents, now part of `off_mission` for every discovery.
   On 26 Oct Google attached FanDuel's and Dimers' odds pages to a tennis
   trend, and the sections list had `/tenis/` but not `/tennis/`.
2. **Not too old.** The trend must have started within 72 hours
   (`MAX_TREND_AGE`), its articles within a week (`MAX_ARTICLE_AGE`), by
   their own time or the date in their path. Not 72 hours for both, as
   the goal first said: a story often breaks before it trends. ABC's
   piece on Netflix's *La Regenta* was dated 23 Oct when its search rose
   on 26 Oct. A week keeps it and still drops r/UpliftingNews' 2016 post.
3. **Not already in the lake**, by host and path, and each URL once: the
   first trend to bring it keeps it.
4. **The mission screen, unchanged**, over every article that passed, in
   one pass. Nothing is exempt, positive signals included.
5. **At most `perSource` articles a trend** (two by default, five at
   most), after the screen. A trend's articles are one story, and
   `SAME_STORY` lists the second after every distinct one.

**The ranking** (`ranking.trend_rank`, `trend_weights`): the story's 0.6
as in any round, split by topic emphasis only when groups were picked
(otherwise the no-topic path, emphasis 0). The source's 0.25 becomes the
**signal's record** in this round's screen: Google's trends keep few,
r/UpliftingNews most. Reliability's 0.15 becomes **virality**: a trend's
place among its own signal's trends, by searches where Google gives them,
else by the feed's order, so each signal's top trend is 1 and ties share
their place. Reliability had to go because nearly every trend article
comes from an unrated domain, at a flat 0.5 that says nothing. A seed has
no virality and counts as unread. The weights sum to 1 at every emphasis
(a test) and are recorded with the round (`ranking.lens: "trending"`).
Reasoned, not fitted: T6's labelled rounds are what will fit them.

**The AI selection** is told when a list is trending (`TRENDING` in
`ai_selector.py`): "score the story, not its popularity", and that
entertainment, celebrity, sport, scandals, accidents and disasters stay
low however viral. Each candidate's line names its trend. It is told only
for a trending round, so a selector called the old way is unchanged.

**Queueing** a trending round notes each queued article's trend card in
`TrendLedger` (`lake/stats/trends/articles.json`, attached by `main.py`
like the sightings), by host and path. The analysis knows nothing of
trends; the writing flow looks the article up (T4, T5).

**On `/discover`**: a dashed Trending button beside the groups; its own
step 2 with the signals to read, a field for "a trend you saw" (a hashtag,
words, a TikTok or news link), the news-search option and the articles
per trend; a "Trending" line on each candidate (name, signal, searches,
since when, whether its TikTok video goes with the story); the trends read
and what became of each; virality in the rank line instead of the rating.

### The lens, run (2026-10-26)

**On the 07:10 Spanish feed, with bge-m3's real screen**
(`test_the_real_screen_puts_the_metro_trend_above_the_lorry_crash`): 30
articles, 9 off-mission by their links (sport and crime sections, the two
betting sites), 9 left out by the screen, 11 offered. The AP-7 lorry crash
was left out as a disaster (margin 0.10). The Línea 10 trend was offered
third, through El Mundo's piece on the metro works. **El País's piece on
the reopening itself was left out as a service page**, at 0.024 against
service's margin of 0.02: the screen reads a transit announcement as a
traffic update. First and second places went to La Voz, a TV talent show
(read as positive, and nearest "celebrity" by 0.009). The screen was not
retuned to pass a test: its margins were measured on 641 candidates.

**Live, every signal, 15:39 UTC**
(`backend/data/evaluation/experiments/trends/first-live-round-2026-10-26.json`):
5 signals, 53 trends (Reddit's top of the day answered this time, with 18
posts), 92 articles; 27 not articles or off-mission, 2 stale, 22 left out
by the screen (two Spanish politics pieces, celebrity rumours, NFL trade
rumours, a winter forecast), **39 candidates in 13.4 s**, no SearXNG.
The first twenty, as ranked:

- 1 and 2: Upworthy's toddler drumming and a tech expert's advice for
  teenagers; 12, a public-speaking expert's "magic phrases". The screen
  has no lifestyle-advice description (tried on 9 Oct, one new catch, not
  adopted), and positive impact's reading rewards feel-good human
  interest (the toddler: 0.98).
- 3, 6, 9, 15: private people being kind or brave, some of them strangers
  in a video.
- 4, 11, 14, 18: the stories the publication is for. Microplastics
  removed from wastewater, a koala park, a solar canopy over a canal,
  tribes bringing back a fish.
- 5: Serbia's election, from r/UpliftingNews, not left out (politics must
  be nearer than every topic).
- 13, 17, 19, 20: Google's US and Spanish trends that passed: an
  antimatter cyclotron, a TV contestant's wife's cancer, an actor's
  birthday, Honda in Formula 1.

So the lens works and is free, but **its order is not yet good**. The
positive-first signals bring most of what the publication wants, mixed
with advice and human interest the screen does not catch, and Google's
trends bring little. Telling them apart is the AI selection's and the
person's job, and T6 measures how well that goes. The toddler at the top
is the privacy rule's case: a story whose subject is a child in a video.

## internet_culture, measured (2026-10-26, T3): not adopted

The plan was a 24th topic, `internet_culture` ("Internet Culture &
Trends", in Culture), for stories whose subject is a trend itself, taking
the three viral keywords Entertainment had gained from the *farmear aura*
article. It was decided by a rule written before the run
(`backend/data/evaluation/experiments/topics24/rule.md`): re-screen the 480
labelled candidates on record under 23 and 24 topics, and adopt only if
the screen leaks and loses little and the Culture group fit neither drops
nor pulls in other groups' stories.

It failed two of four checks (`docs/experiments.md`, "topics24"). Culture's
group-fit AUC fell from 0.9014 to 0.8785, by 0.023 against a bound of
0.02. Thirteen stories of other groups would newly fit a Culture round,
against a bound of three: a water-lily species found on Instagram, a
school-lunch story, a hospital dog, two election polls. The screen itself
barely changed (one not-worth-offering story back in, none lost). A
topic about social media draws whatever mentions a platform: the
stories now nearest it were Meta, a TikTok lawsuit, Zuckerberg, Celebrity
Traitors and Shakira.

So `src/config/topics.py` keeps its 23 topics and Entertainment its three
viral keywords; the labeller is unchanged. A trend's article is
classified by what it is about, which is also why Trending is a lens and
not a group. The proposed definition lives in
`src/evaluation/trend_experiments.py`, so the run can be repeated.
Because T3 now comes before T6, all five trend rounds run on this
23-topic screen.

## Five trending rounds, labelled blind (T6, RQ1): day 1 of 5

The rule was written before the first day
(`backend/data/evaluation/experiments/trends/rule.md`). Each day, one
trending round (every signal, no seed, no news search, two articles a
trend) and the day's topic rounds over all five groups, made by
`uv run python -m src.evaluation.experiments trends run` through the
app's own services, so a person can open them on `/discover`. The
trending round's first twenty go to `to-label.json`, shuffled and with
no score. They are labelled 0/1/2, with the angle (`story`, `possible`,
`none`) and whether the subject is a private person, and then
`trends report` (`src/evaluation/trend_experiments.py`) reports them.

**Day 1, 2026-10-26, 15:5x UTC**, labelled by Claude, blind to the scores,
not yet checked by the author:

- 53 trends, 92 articles, 40 kept by the screen, 39 offered.
- First twenty: **12 worth offering (0.60), 5 clearly positive (0.25)**.
  Angle: 10 `story`, 1 `possible`, 9 `none`. **5 had a private person or a
  child as their subject.**
- **All 12 were new**: neither of the day's topic rounds offered them, by
  link or by title similarity (bge-m3, `SAME_STORY`).
- By signal: r/UpliftingNews 9 of its 10 worth offering (4 clearly
  positive); Upworthy 2 of 6; Google Trends 1 of 4 (Spain's PEGI loot-box
  rating, clearly positive; the US's GPU hack and an actor's birthday,
  not).
- Chosen, admitted, published: none yet. The rounds wait on `/discover`.

One day decides nothing (rule.md). Days 2-5 are the author's, one a day:
`trends run`, label `to-label.json` into `labels.json`, `trends report`.
After five days the rule decides three things: whether the lens stays
(at least 10 new stories worth offering), whether a signal is disabled
by default (80% not worth offering, with at least 10 labelled), and
whether the trend weights are refitted (100 labelled).

## The angle (built 2026-10-26, T4)

**An angle is found, never invented.** When a draft is written from an
article a trending round brought (`TrendLedger` says which), the writer
model proposes at most `angle_max_proposals` (3) constructive angles.
Each angle is a question a reader would ask, a news query, and one
checkable claim, in the article's language
(`src/services/trends/angles.py`, `AngleFinder`). Each claim goes through
the fact-checker's own `check_claim`, the path `POST /verify-claim`
takes, with the article as context so it cannot confirm its own angle.
It is **kept** only when the verdict is TRUE and its cited, supporting
sources come from at least `angle_min_domains` (2) domains other than the
article's own outlet. Every other outcome is a refusal that says why
(FALSE, UNVERIFIED, one domain, search or verifier unreachable). The
model is told that no angle is a good answer and never to write a bright
side for an accident, a war, a crime, a death or a scandal.

- **Refused before any model is asked** when the mission screen reads the
  article's headline and lead as a disaster, war, crime or death report,
  and also when the screen cannot be asked at all: conservative before
  viral. An article reaches a draft only after passing the round's
  screen, but a seed's news link or a round whose screen was down may not
  have been screened.
- **In the writing flow, not the analysis**: no `on_phase` stage
  (invariant 6), and the analysis cache is untouched. The two minimums
  are `WriterThresholds` fields with settings defaults
  (`WRITER_ANGLE_MAX_PROPOSALS`, `WRITER_ANGLE_MIN_DOMAINS`) and request
  overrides (invariants 1-2).
- **On the draft**: `ArticleDraft.trend` (`DraftTrend`) holds the card,
  every angle kept or refused with its reason, verdict, confidence and
  domains, and why none was looked for. The kept angles' supporting
  sources join the draft's sources with origin `angle`, after the related
  news and before the fact-check evidence.

### The angle, tried (2026-10-26)

One real trend article from day 1's round: r/UpliftingNews' "Princeton
alumni remove microplastics from Atlantic City wastewater" (whyy.org),
analysed by the app's own pipeline. The writer was `writer` (qwen3.5:4b,
16k, thinking off), set for the trial only; this machine's `.env` names
none. The verifier was llama3.2:3b, with SearXNG up (Google refusing,
Brave rate-limited). Record:
`backend/data/evaluation/experiments/trends/angle-trial-2026-10-26.json`.

- The analysis took 162 s: 6 claims, overall UNVERIFIED (one of them
  unverified), published by the reader.
- **The angle step took 131 s for three angles**, about 44 s each:
  - **Kept**: "Former Princeton University graduates founded PolyGone
    Systems and designed a new treatment method for the Atlantic County
    Utilities Authority." TRUE at 92%, supported by 4 domains (The
    Overhead Wire, Pulse 2.0, WJRZ, a press-release mirror).
  - **Kept, on weak ground**: "The technology replicates ultrahydrophobic
    plants found in wetlands...". TRUE at 65%, and its two domains were
    Wikipedia's page on ultrahydrophobicity and a dictionary entry. They
    confirm the concept, not PolyGone's use of it. This is the known gap
    (CLAUDE.md, "Nothing measures whether a source is on-point about the
    *right* subject"), now inside the angle step: the per-source verifier
    said "supports" to pages about the same idea that make a different
    claim.
  - **Refused**: the environmental impact. TRUE, but supported by one
    domain.

The angles mostly restated the article (founding, mechanism) rather than
finding a new constructive thread, because the article was good news
already, a positive-first trend. The case the step exists for, a
neutral trend with an angle (Netflix's *La Regenta*), was not tried
here: its article was not in the day's first twenty. **The second
angle's weak support is a reason to read the reasons on the draft
before taking an angle**, not to trust "kept" alone.

## The story (built 2026-10-26, T5)

- **The writer** is told the trend (never as evidence: "popularity
  proves nothing", and "trending" only if a source says so) and each
  confirmed angle with its sources as `[n]`. It may take one or none.
  With none confirmed it is told to add no bright side. `CLOSED_WORLD_RULES`
  are unchanged; an angle source is a numbered source like any other,
  labelled "a source behind a confirmed constructive angle".
- **The review** (`apply_angle_check` in `draft_reviewer.py`, with
  `grounding.stating`, the echo rule that already finds a repeated
  FALSE claim): a sentence that states a kept angle's claim must cite one
  of that angle's own sources, and the review says so when it cites
  another source or none. When no angle source is cited at all, the
  review notes that no angle was taken. These are issues only, with no
  ceiling: an uncited sentence is already capped by the grounding check,
  and taking no angle is the writer's choice.
- **Publishing**: the snapshot gains `trend` (the name, the signal and
  the video), copied field by field like the rest. The angles, the
  searches and the trend's link stay the newsroom's.
  A video is published only with a numeric player id and a TikTok link
  (`story_trend`), so what the page loads after the click is fixed on
  the server, not by the draft.
- **The reader** (`TikTokVideo.tsx`) shows the video behind a facade that
  names TikTok and its cookies, with a plain link to open it on TikTok.
  `https://www.tiktok.com/player/v1/<id>` is loaded, sandboxed, only after
  the reader clicks. The story's disclosure says it was found through a
  trend and that popularity proves nothing, in Catalan, Spanish and
  English (the Spanish and Catalan by the AI, like the reader's other
  strings, until a native speaker reads them).
- **/drafts/[id]** gets a "From a trend" panel: the trend, the video, and
  every angle kept or refused with its reason and its sources by number.

**Checked**: `./scripts/check.sh e2e` holds that a story from a trend
loads nothing from TikTok until the click. Chrome resolves `tiktok.com`
to a local port that only counts connections, so an https request, a
preconnect or a plain request is counted alike. The same checks were run
on this Windows machine (`--dump-dom`, and a click over DevTools on a TCP
port): the facade rendered, **0 connections to TikTok before the click**,
the player's iframe after it, and 2 connections. The e2e script itself
still needs a POSIX machine for its DevTools pipe. On the way, its
`--dump-dom` reader decoded Chrome's UTF-8 as the platform's code page
(cp1252 on Windows), and now says UTF-8. The click is also only sent once
React has hydrated the button: a click on the server's HTML did nothing.

### The story, tried (2026-10-26)

A draft from the article of the angle trial, in English, written by
`writer` (qwen3.5:4b) and reviewed by `reviewer` (qwen3.5:9b), both set
for the trial only, through `get_draft_writer()` and
`get_draft_reviewer()` as the app builds them. Record:
`backend/data/evaluation/experiments/trends/story-trial-2026-10-26.json`.

- **355 s from request to draft**: the related news (four of its pages
  refused with 403 or 429, one timed out), the angle step run again, and
  the write. **The review took 289 s.** The angle step, searched a second
  time, kept the same two claims but not on the same footing: the
  founding at 81% from three domains (92% from four the first time), the
  wetland plants again at 65% from Wikipedia and the dictionary, and the
  third refused as FALSE where the first run had found one domain. The
  same pipeline searched twice moves (CLAUDE.md); an angle does too.
- The trend's two kept angles brought four sources, [7]-[10]. The body
  cites three of them: [7] and [8] for the seed round, and [9], the
  dictionary entry, for "This mechanism mimics natural processes where
  specific plant structures attract and capture contaminants". **The
  weak angle reached the story**, cited. That is what the draft's angle
  panel is for, and why "kept" is not enough to take one.
- **The review flagged two sentences, both grounded.** The first sentence
  (the founders, the plant) cites [1], the analysed article; the
  mechanism sentence cites [4], The Overhead Wire's copy of the same
  WHYY story. Both say what the sentence says. The angles restated the
  article, as a positive-first trend's angles will, so a sentence can
  state an angle's claim from the article rather than from the angle's
  sources. The check works as written: it raises an issue and lowers no
  score. Not changed on one trial. If the days' drafts show the same,
  the check should skip a claim the analysed article itself states.
- The copy check found three passages taken word for word from the
  article; readability scored 36.4 and coverage of the verified claims
  51.8, the two lowest of the review's scores.
