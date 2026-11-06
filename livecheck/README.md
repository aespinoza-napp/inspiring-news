# livecheck

Listens to a conversation you are watching and, from its sound alone, writes
what is said, tells who asks from who answers, judges whether each question was
answered and sends the answers' factual statements to the project's
fact-checker. At the end it writes a report.

```bash
cd livecheck && uv sync

# Play the live stream in your browser, then:
uv run livecheck apps                  # what is playing, e.g. "brave"
uv run livecheck listen --app brave    # only that application's sound
uv run livecheck listen                # everything the machine plays

uv run livecheck file talk.mp3         # a recording instead
uv run livecheck report sessions/<dir> # write a session's report again
```

Ctrl-C once stops listening and lets the queued checks finish; twice closes at
once, and what was not checked is reported as not checked. The report is
`sessions/<date>/report.md`, with `report.json` beside it and everything that
happened in `events.jsonl`. `sessions/` is not committed: it holds other
people's words.

The first run downloads Whisper `small` (about 460 MB, Hugging Face) and the
voice model (about 26 MB, GitHub) to the user's cache.

**What it needs running.** Words and voices need nothing else. Judging answers
needs Ollama. Truth needs the backend, `./scripts/stack.sh analyse`. If either
is missing the session still runs, and its report says what could not be done.

## Why it hears the sound card

It never contacts YouTube. Downloading from it is against its terms, and the
request was audio only, so the tool records what already plays on this machine
with `parec`: any site, no URL, no key. The microphone is never opened. Without
`--app`, a notification sound or a second tab gets into the transcript; with it,
a muted tab is silence (the tool says so after 30 s).

## How it works

```
parec -> voice activity -> Whisper -> sentences -> voice model -> roles
 hear     cut at pauses      words     with times    who spoke    who asks
                                                                     |
report <- fact-checker <- statements from answers <- was it answered?<-+
          POST /verify-claim    (Ollama)                (Ollama)
```

Each stage is its own thread, because they run at very different speeds: the
words keep up with the stream while the fact-checks fall behind and catch up
after the end. If the words themselves fall more than 60 s behind, speech is
skipped and the report says how much.

| Decision | Why |
|---|---|
| A voice is a cluster of sound, compared by cosine (`SpeakerTracker`) | Nobody says who is talking or how many there are |
| Roles are read from behaviour: who asks most | Nobody is introduced. Roles can change early on, so everything is rebuilt from the whole conversation |
| Speakers are settled once more at the end, for the report | A speaker's average early on rests on a few seconds. **So the report can differ from what the screen showed** |
| A claim a model wrote is dropped unless its figures and most of its words are in the transcript | A statement the person never made, listed under their name as false, is the worst mistake this tool can make |
| A failed search or model is "not checked", never "no verdict" | The pipeline returns UNVERIFIED for both, and they mean different things |
| At most 30 claims per session (`--max-claims`) | A claim takes most of a minute. The rest are listed as not checked |

## What it gets wrong

Measured limits are in the section below. By construction:

- **Two voices at once**, and interruptions, go to one speaker or the other.
- **A sentence holds one speaker.** A turn that changes with no pause and no
  punctuation stays with the first.
- **Short replies ("yes", "no")** under half a second go to the last speaker,
  because they hold too little voice to tell. A bare "yes" can therefore read as
  the interviewer's, leaving the question looking unanswered.
- **Questions without a question mark** depend on Whisper's punctuation and a
  short list of forms in English and Spanish.
- **Debates:** one role per voice for the whole session. Two people questioning
  each other get one "asks" and one "answers".
- **Only `en` and `es`** are checked by the fact-checker's lexicons.
- **The fact-checker's verdicts are often wrong**: see "The LLM's accuracy" in
  the root `CLAUDE.md`, and its figures on altered claims. The report says so at
  the top, and every verdict lists its sources and timestamp to go back to.
