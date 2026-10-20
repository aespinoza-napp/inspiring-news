# Five readers try the reader view (RQ4, the reader's side)

The roadmap item "Five readers try it" (Phase 6) and `docs/goals.md`, U5.
Prepared 2026-10-20; the sessions are the author's to run. This page fixes
the protocol before the first session, so the five are run alike and the
results cannot shape the questions.

## What it asks

Whether a reader who is not the author can tell, from the public pages
alone, **what was checked and how**:

1. **Why** a claim was judged as it was.
2. **FALSE against "Not checked"**: a finding about the claim against a
   failure of ours.
3. **Who wrote** a story: a person, or a model approved by a person.

## Who

Five people who are not the author and did not build the system; none
need know anything about fact-checking. At least two read Catalan or
Spanish, so the translated pages are tried as well as the English (the
native read of U4 comes first, if it can). Recorded by initials only, with
the language they used and whether they read news online most days.

## Before the first session (once, then frozen)

- **The stack**: the reader served as a reader meets it - `/reader` in a
  normal browser window, not the operator pages. Confirm `/healthz` and
  that the feed shows articles.
- **The material**, chosen once and written here before any session, so
  every reader sees the same pages:

  | Task | Page | Chosen (fill in) |
  |---|---|---|
  | 1 | An article with at least three claims, one of them with cited sources and a quote | `/reader/<id>` |
  | 2 | An article with one claim "Not checked" beside judged ones; and the guide | `/reader/<id>`, `/reader/guide` |
  | 3 | One published story | `/reader/stories/<id>` |

- **Task 2's constraint.** The public reader never shows a FALSE claim: an
  article takes its worst claim's verdict, and a FALSE or MISLEADING
  article is not publishable. So FALSE can only reach the reader through
  the guide. **Recommended:** ask the reader to point at the "Not checked"
  claim, say what it means, and then, using the page and its guide, say
  how a FALSE claim would differ. The alternative - a printed panel of a
  FALSE claim from an operator page - mixes in a page readers never see.
  The author decides before the first session; note the choice here.

## Each session (about 15 minutes)

Say, and only this: *"This is a news site that checks the claims in the
articles it shows. I will ask you three things. Use only what is on the
screen; think aloud if you like. There are no wrong answers - I am testing
the page, not you."* Ask consent to note answers by initials. Then the
three tasks, in the same order, each from the page named above, with a
timer from the question to the answer.

Do not explain, hint or point. If asked "what does X mean?", answer *"What
would you guess from the page?"*. Stop a task at 3 minutes and record it
as not done.

| Task | The question, as said | Success means |
|---|---|---|
| 1 | "Why do you think the site judged this claim as it did?" (point at one claim) | They name the evidence: a source, its stance or the quoted passage, or the explanation, as the reason |
| 2 | "What does 'Not checked' mean here? And how would a claim marked FALSE be different?" | Not checked is ours (the search or the model failed), not a finding about the claim; FALSE is a finding that the evidence contradicts it |
| 3 | "Who wrote this article?" | A model wrote it and a person approved (or edited) it, read from the disclosure |

## One sheet per reader

```
Reader: __ (initials)   Language used: ca / es / en   Reads news online most days: yes / no   Date:

Task 1  done: yes / partly / no   time: __ s
        what they said:
        what confused them:
Task 2  done: yes / partly / no   time: __ s
        what they said:
        what confused them:
Task 3  done: yes / partly / no   time: __ s
        what they said:
        what confused them:
Anything else they remarked on:
```

"Partly" is a right answer reached with a wrong reason, or half of task 2.
Write what they said in their words, briefly; the judgement of success is
made afterwards against the table above, not during the session.

## Afterwards

Per task: successes out of 5 (partly apart), the median time, and the
confusions grouped by what caused them, each quoted by initials. Recorded
in the RQ4 section of `docs/decisions/evaluation.md`, the roadmap item and
the thesis (Chapter 7, RQ4). A confusion that needs a change to the pages
becomes its own roadmap item; nothing is fixed between sessions, or the
five would not have seen the same pages.
