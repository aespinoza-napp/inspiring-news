---
name: write-constructive-article
description: Write an Inspiring News (constructive, Positive edition) article (or judge one) from a draft's numbered sources and fact-checks, the way the newsroom wants it since 10 Nov 2026 - 800 to 1,200 words for readers aged 15 to 30, in five parts (what happened, why it matters, who it reaches, how it works, what is still open), warm and human, and closed-world - every fact cited from the sources, no effect on people or the environment the sources do not state. Use when asked to write, extend or improve a constructive / Positive-edition article from a draft, to show what the writer model should produce, or to judge such a draft against the house style. For a Devastating-edition draft use /write-devastating-article instead.
---

# Writing a constructive article for Inspiring News

**Positive edition only.** A draft whose `edition` is `devastating` is written with
`/write-devastating-article`: another voice, no fact-checks, no five parts. Check
the draft's `edition` first.

The writer model (`backend/src/services/writer/article_writer.py`) is told the same
premises in `READERS` and `ARTICLE_PARTS`. **This skill and that prompt are one
style**: change one, change the other in the same commit
(`backend/tests/services/writer/test_article_writer_readers.py` holds the parts'
names equal). `docs/decisions/writing.md`, "Writing", has the why.

## Who reads it

**15 to 30 years old.** They read on a phone, between other things, and leave at the
first paragraph that does not tell them why they should care. Write for them:

- **Plain, direct and warm.** Short paragraphs (2-4 sentences), sentences of varied
  length, active verbs. Every technical term, institution or acronym explained in
  plain words the first time - from what the sources say about it.
- **Human first.** Open with the people or the place, as the sources describe them:
  who is affected, what changes in their day. "You" (Spanish *tú*) only to say why it
  matters to the reader, never to tell them what to feel.
- **No slang, no emojis, no talking down, no hype.** Constructive is not cheerful:
  report what works, for whom, with what evidence, and its limits.

## The five parts

In this order, each under a `## ` subheading **in your own words** (never these
labels):

1. **What happened** - the news in the first paragraph, and the people or place
   behind it.
2. **Why it matters** - the problem it answers: how big, how long, what was tried
   before.
3. **Who it reaches** - what changes for people (patients, students, workers,
   families, a town) and, *where the sources say so*, for the environment, the
   economy or the community. Concrete examples, figures, voices.
4. **How it works** - the method, the evidence it works, what it costs, who pays,
   who takes part.
5. **What is still open** - limits, risks, criticism, what has not been shown yet,
   what comes next.

**800 to 1,200 words** unless the editor's instructions say otherwise. The length
comes from using *more of the sources* - their details, figures, examples and the
words of the people in them. Never from repeating, padding or adding.

## Extending without inventing

The author wants more than the bare news: context, the people, the effect on them
and on the environment. That is exactly where an article starts to invent - an effect
that *sounds* likely ("this will reduce emissions", "families will save money") is a
hallucination when no source says it. So:

- **Every factual sentence ends with `[n]`**, the source it comes from (`[2][4]` for
  two). Only numbers from the draft's sources.
- **Every number, name, date and quote is in a source as you use it.** Quote only
  words a source puts in quotation marks, and say who said them.
- **Where the sources are silent on a part, leave it out**, or say in one sentence
  that it is not yet known ("Todavía no se sabe cuántos pacientes..."). Never fill it
  from what you know - you know a lot, and none of it is in the closed world.
- **The fact-checks decide what may be stated:** `TRUE` as fact; `PARTIALLY_TRUE`
  only the supported part, saying what is disputed; `FALSE`/`MISLEADING` never as
  fact, only to say it was found so; `UNVERIFIED`/`NOT_CHECKED` left out or
  attributed to [1] as unconfirmed.
- **Source [1] is someone else's article:** your own words, never more than a few of
  its words in a row.
- To extend, **read every source to the end** first: the related news and the
  evidence pages usually hold the figures, the history and the people that [1] only
  mentions. That is the material for parts 2-4.

Markdown only as the page renders it: paragraphs, `## `/`### `, `- ` lists, `**bold**`.
No links, images, tables, or a title inside the body.

## How to do it

1. **Get the material.** A draft id: `curl -s -H "X-API-Key: $STORAGE_API_KEY"
   localhost:8000/drafts/<id> > <scratchpad>/draft.json` (or copy it from the
   backend container, `/app/data/drafts/<id>.json`). Read `sources` (each one's
   `excerpt` is exactly what the writer saw), `factChecks`, `language`, `edition`,
   `instructions`.
2. **Plan before writing**: for each of the five parts, list the facts that go in it
   and their `[n]`. A part with nothing is left out - say which, and why.
3. **Write** in the draft's language, to `<scratchpad>/article.md`: `# Title` on the
   first line (under ~60 characters), the subtitle on the next, then the body.
4. **Check it** with the app's own checks (no model, nothing written):

   ```bash
   cd backend && uv run python ../scripts/check_article.py \
       --draft <scratchpad>/draft.json --article <scratchpad>/article.md
   ```

   Fix until `unsupported`, `uncited`, `dangling` and `repeatsUnconfirmedClaim` are
   empty and `words` is in range. `uncitedButInSource` names the source to cite.
   The check is word overlap: it cannot tell a sentence that is in a source from one
   that only shares its words, and a name or place with no figure beside it passes
   unseen. **Reread every name and place against the sources yourself.** Found on the
   first try of this skill (New Heart, 10 Nov): "tus abuelos en un pueblo de
   Ourense" - cited, checked clean, and Ourense is in no source. `findings` also lists
   a quotation as "copied word for word" from [1]: a quote attributed to who said it
   is allowed (rule 3); an unquoted copied run is not.
5. **Report** the article, its word count, which parts were left out for lack of
   sources, and the check's result.

## What not to do

- **Never save it into the draft through the API as an edit.** A person's edit is
  disclosed on the published page as "edited and approved by a person"; text Claude
  wrote is not that. Hand it to the author, who decides.
- **Not for the Devastating edition**: `/write-devastating-article`.
- To judge a draft instead of writing one, run step 4 on its current text and read
  it against the parts and the premises above: say what each part is missing and
  which source holds it.
