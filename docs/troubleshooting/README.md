# Troubleshooting, process by process

One folder per process of the app, each checked part by part against a person-like
reader (Claude, blind) on the same inputs. Inside each: one file per part, upstream
first, and `experiments/<part>/`, one file per experiment on that part.

| Process | Folder | State |
|---|---|---|
| Fact-checking a claim | [fact-checking/](fact-checking/README.md) | 5 parts; the 4 Nov comparison (20 claims); the agent script (`scripts/troubleshoot.sh`) |

A new process gets its own folder with the same shape: a `README.md` (what was compared,
how, the headline table), `NN-<part>.md` per part (the finding, what was built, what to
try) and `experiments/NN-<part>/`.
