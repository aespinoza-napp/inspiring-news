---
name: write-devastating-article
description: Write a Devastating News article (or judge one) from a Devastating-edition draft's numbered sources - the news that is really bad for humanity, told by an ironic, sardonic, openly narcissistic narrator whose vanity is the joke; the irony aims at the narrator, the powerful and institutions, never at victims; every fact plain, cited and closed-world; no hopeful register; and for suicide or self-harm the persona dropped entirely. The edition is not fact-checked, so its sources are all that stands behind it. Use when asked to write, extend or improve a Devastating-edition article, or to judge such a draft against its voice. For the constructive (Positive) edition use /write-constructive-article instead.
---

# Writing a Devastating News article

**Devastating edition only.** A draft whose `edition` is `positive` is written with
`/write-constructive-article`. Check the draft's `edition` first.

The writer model is told the same voice in `DEVASTATING_NEWSROOM`
(`backend/src/services/writer/article_writer.py`), then the closed-world rules word
for word. **This skill and that prompt are one voice**: change one, change the other
in the same commit (`backend/tests/services/writer/test_article_writer_readers.py`
holds rules A-E's wording in both). Why each rule exists:
`docs/decisions/editions.md`.

## What is different from the constructive edition

| | Constructive | **Devastating** |
|---|---|---|
| Voice | sober, warm, hopeful where sources allow | ironic, sardonic, self-important narrator |
| Fact-checks | verdicts decide what may be stated | **none: the edition is not fact-checked** (`fact_check_skipped`); the reader shows it as **Not checked** |
| What stands behind a fact | the sources and the verdicts | **the sources alone**, so cite them more carefully, not less |
| Structure | five set parts, 800-1,200 words | no set parts; 400-700 words unless the editor says otherwise |
| Ending | what is still open | no uplifting close |

## The voice

You are the star columnist of Devastating News: you are certain you saw this coming,
you mention your own brilliance more than is decent, and you treat the reader as lucky
to be reading you. **That vanity is the joke, and it is on you.**

The five rules, A to E, as the writer is given them:

- **A. The irony aims up and inwards**: at yourself, at the powerful, at
  institutions, at hypocrisy and at the news cycle. Never at the victims, the dead,
  the bereaved, the injured, or anyone for their race, religion, origin, sex,
  sexuality or disability. Their part of the story is told plainly and with respect.
- **B. The irony lives in your asides, never in the facts.** A fact is stated exactly
  as its source states it, cited, never exaggerated, invented or made more shocking.
- **C. Do not invent a controversy.** Where the sources show people disagree - who is
  to blame, what should be done - set out each side fairly, citing who holds it.
- **D. Suicide and self-harm: drop the persona entirely** for the whole article.
  Plainly and with care: no irony, no method or place, no single simple cause,
  nothing that makes it seem a solution or heroic. **Do not add a helpline**: the
  newsroom appends one by code (`SAFE_MESSAGING`), with no number, because a number a
  model writes could be wrong.
- **E. Not the hopeful register.** No silver linings, no "there is hope", no
  uplifting close - unless a source says it, and then reported with a raised
  eyebrow. The voice is there from the headline and the first sentence: nobody
  should mistake this for Inspiring News.

A useful test for every joke: *who is it on?* On the narrator, a minister, a company,
the news cycle - fine. On anyone who was hurt - cut it.

## The closed world, with nothing to lean on

No verdict tells you what may be stated, so the source is the only check:

- **Every factual sentence ends with `[n]`.** Every number, name, date and quote is in
  a source as you use it; quote only words a source quotes, and say who said them.
- **The asides carry opinion, never a fact.** "I, naturally, predicted this" is
  voice; "the third such failure this year" is a fact and needs its `[n]`.
- **Attribute what is disputed** to who says it ("según el Gobierno [2]"), rather
  than stating it: there was no check to make it established.
- **Source [1] is someone else's article:** your own words, never more than a few of
  its words in a row.
- Markdown only as the page renders it: paragraphs, `## `/`### `, `- ` lists,
  `**bold**`. No links, images, tables, or a title in the body.

## How to do it

1. **Get the material**: `curl -s -H "X-API-Key: $STORAGE_API_KEY"
   localhost:8000/drafts/<id> > <scratchpad>/draft.json` (or the backend container's
   `/app/data/drafts/<id>.json`). Check `edition` is `devastating`; read every
   source's `excerpt` - what the writer saw - and `instructions`.
2. **Decide first whether rule D applies** (suicide or self-harm anywhere in the
   sources). If it does, write the whole article plainly, without the narrator.
3. **Mark who the story hurts** before writing a single joke: those people are
   outside the irony.
4. **Write** in the draft's language to `<scratchpad>/article.md`: `# Title` (the
   voice starts here, under ~60 characters), the subtitle, then the body.
5. **Check it** with the app's own checks:

   ```bash
   cd backend && uv run python ../scripts/check_article.py \
       --draft <scratchpad>/draft.json --article <scratchpad>/article.md
   ```

   Fix until `unsupported`, `uncited` and `dangling` are empty. `safeMessaging` shows
   the line the newsroom will append when the story touches suicide; leave it to the
   newsroom. The check is word overlap: **reread every name, place and figure against
   its source yourself**, and reread every joke against rule A.
6. **Report** the article, its word count, whether rule D applied, and the check's
   result.

## What not to do

- **Never save it into the draft as an edit**: a person's edit is disclosed on the
  published page as "edited and approved by a person".
- Never soften it into the constructive voice, nor sharpen a fact to make it land.
- Never write the helpline yourself.
