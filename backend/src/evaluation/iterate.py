"""
The iteration loop: an agent proposes one change to the fact-checker at a
time, the harness measures it on the train half, and a rule written
before the first try decides it (docs/decisions/evaluation.md, "The
iteration loop"; the `iterate-fact-check` skill drives it).

A campaign is a directory under data/evaluation/experiments/iterate/:

    campaign.json   what is compared with what, the target, the budget
    rule.md         the rule, as written at `init`; editing it ends the campaign
    ledger.jsonl    append-only: every try proposed, then decided

Why each piece is the way it is:

- **The hypothesis is written before the run** (`propose`), with what it
  is expected to do, so a result cannot choose its own story. The ledger is
  append-only for the same reason: a try that lost stays on the record.
- **Every try is compared with one fixed baseline, never with the best try
  so far.** Hill-climbing on 69 claims, each step a "win" inside its own
  interval, is fitting the train half. A combination of kept tries is a try
  of its own, judged against the same baseline.
- **Fixed evidence wherever possible.** Two searched runs of the same
  pipeline differed by 6-9 points from the web alone, so a change after
  retrieval is replayed on one searched run's evidence (`--replay`). A
  change the replay cannot see - what is searched, how many pages are
  read, restating the claim, the second look - is a searched try, judged
  against two searched baselines made in the same window, and must beat
  the gap between them.
- **The train half only.** `score` refuses any run that is not over the
  campaign's own claims; the test half is the author's, once, at the end
  (`.claude/hooks/sealed_test_half.py` keeps the agent away from it while
  a campaign is active).
- **Time counts.** The target is the 20-second fact-check
  (docs/decisions/performance.md): a claim's median at most 20 s, its 90th
  percentile at most 30. A replay does no search, so its seconds are the
  replay's own (ranking, the model, the scorer) plus what retrieval took
  for that claim in the run replayed.
"""

import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from src.config.settings import settings
from src.evaluation import metrics
from src.evaluation.effort import confidently_wrong
from src.evaluation.replay import EVIDENCE
from src.evaluation.report import compare, load_run, write_report
from src.evaluation.runner import default_runs_root, thresholds_hash
from src.evaluation.stats import median, percentile, rounded

RULE_VERSION = 1

CAMPAIGN = "campaign.json"
RULE = "rule.md"
LEDGER = "ledger.jsonl"

ACTIVE = "active"
CLOSED = "closed"

# What a try changes. `search` and any change the replay cannot see are
# searched tries; the rest are replayed.
KINDS = ("baseline", "thresholds", "prompt", "model", "code", "search")

# Decisions. `continue` is a screen that passed: run the rest of the claims.
KEEP = "keep"
REJECT = "reject"
SCREENED_OUT = "screened-out"
INVALID = "invalid"
CONTINUE = "continue"
REGISTERED = "registered"

# Thresholds a replay cannot measure: they act inside or before
# EvidenceRetriever.retrieve, which a replay answers from the file.
# `claim_restatement` changes the text searched (the replay looks claims up
# by it); the second look searches again; the deadline gives pages half of
# a claim's budget. `max_evidence_per_claim` is both: retrieval fetches that
# many pages, ranking keeps that many, so a replay can lower it but not
# raise it (`search_side_changes`).
SEARCH_SIDE = (
    "query_kinds",
    "evidence_fetch_candidates",
    "evidence_prerank",
    "fetch_evidence_pages",
    "claim_restatement",
    "second_look_enabled",
    "second_look_below_confidence",
    "claim_deadline_seconds",
)

# What a field did in runs from before it existed (their run.json has no
# value for it, or null).
_BEFORE_IT_EXISTED = {
    "claim_restatement": "off",
}

# Code a replay never runs: a change here makes a try a searched one.
# terms.py is shared by query building and by lexical ranking, so it counts
# here: it changes what is searched.
SEARCH_SIDE_PATHS = (
    "backend/src/services/fact_checker/retrieval/",
    "backend/src/services/fact_checker/restatement.py",
    "backend/src/services/fact_checker/second_look.py",
    "backend/src/services/fact_checker/terms.py",
    "backend/src/services/scraper/",
    "backend/src/services/search.py",
)

# Where the code that can change a verdict lives: a try that changes code
# must have it committed, so the commit a run records is the code it ran.
CODE_PATHS = ("backend/src/",)

DEFAULT_TRIES = 15
DEFAULT_SCREEN = 20
TARGET_MEDIAN = 20.0
TARGET_P90 = 30.0

# The rule's numbers, each in claims of the paired set, not percentage
# points: on 69 claims one claim is 1.4 points.
SCREEN_OUT_NET = -3        # three more claims wrong than the baseline on the screen
SCREEN_OUT_SLOWER = 1.5    # half as slow again, and no claim gained
WORSE_NET = -2             # two more claims wrong
WORSE_CONFIDENTLY_WRONG = 1
SAME_FOR_SPEED_NET = -1    # a speed gain may cost at most one claim
FASTER = 0.9               # a median at least 10% lower
SET_APART_SLACK = 1        # "not checked" or errors beyond the baseline's


RULE_TEXT = f"""# The iteration loop's rule (version {RULE_VERSION})

Written by `cli iterate init` before any try. Editing this file ends the
campaign: `score` refuses to decide against a rule that changed.

Every try is compared, paired claim by claim, with the campaign's
**baseline** (the defaults replayed on the evidence run, try 0), never with
another try. Counts are in claims of the paired set.

## Valid at all

- The run is over the campaign's claims (same dataset file, the train
  half), with the label, model and thresholds `propose` recorded, and - for
  a replay - replays the campaign's evidence run.
- It sets apart (error, not checked, search unavailable) at most
  {SET_APART_SLACK} claim(s) more than the baseline does on the same claims.
  A claim set apart drops out of both sides of the comparison, so without
  this a try could improve its accuracy by giving up on its hard claims.

## The screen (the first claims only)

A try is first run on the first `screen` claims. It is **screened out**
when it gets {-SCREEN_OUT_NET} or more claims wrong that the baseline got
right, net, or when its median claim is {SCREEN_OUT_SLOWER}x the baseline's
with no claim gained. Otherwise it runs on every claim (the same run,
resumed).

## The decision (every claim)

Quality, against the baseline:

- **better**: the paired accuracy difference's 95% interval is above zero
  and it is confidently wrong (a definitive verdict that is not gold) no
  more often;
- **worse**: {-WORSE_NET} or more claims wrong net, or confidently wrong
  more than {WORSE_CONFIDENTLY_WRONG} more time(s);
- **same**: anything else ("no detectable difference" is a result).

Speed: **meets the target** when a claim's median is at most
{TARGET_MEDIAN:g} s and its 90th percentile at most {TARGET_P90:g} s (the
campaign may set others); **faster** when the median is at most
{FASTER:g}x the baseline's. A replay's seconds are its own plus what
retrieval took for that claim in the evidence run.

**Keep** when better, or when the same, at most {-SAME_FOR_SPEED_NET} claim
lost net, confidently wrong at most {WORSE_CONFIDENTLY_WRONG} more, and
faster or meeting the target. **Reject** otherwise.

## Searched tries

A try the replay cannot see (what is searched, how many pages, the claim
restated, the second look, the deadline, or code on the search side) is
run with its own search. It is compared with **two searched baselines**
made back to back in the same window, and the gap between them (claims
wrong net) is the noise: it is **better** only when better against both and
its net gain exceeds that gap; **worse** when worse against both. Its
seconds are its own, as measured.

## The end

The campaign stops when its tries are spent or a kept try meets the target.
Nothing a campaign keeps becomes a default: the best kept try goes to the
test half once, run by the author, and is adopted only if it holds there
(the `fact-check-change` skill).
"""


# ----------------------------------------------------------------------
# Files
# ----------------------------------------------------------------------


def default_campaigns_root() -> Path:

    return Path(settings.STORAGE_PATH) / "evaluation" / "experiments" / "iterate"


def _now() -> str:

    return datetime.now().astimezone().isoformat(timespec="seconds")


def _sha256(path: Path) -> str:

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict:

    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: dict) -> None:

    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


@dataclass
class Campaign:

    directory: Path
    config: dict
    entries: list[dict] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.config["name"]

    def save(self) -> None:
        _write_json(self.directory / CAMPAIGN, self.config)

    def append(self, entry: dict) -> None:
        """One ledger line. Never rewritten: a correction is a new line."""

        with (self.directory / LEDGER).open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

        self.entries.append(entry)

    def tries(self) -> dict[int, dict]:
        """Each try folded from its ledger lines: the proposal, then the latest decision."""

        folded: dict[int, dict] = {}

        for entry in self.entries:

            number = entry["try"]

            if entry["event"] == "proposed":
                folded[number] = {**entry, "decision": None, "decisions": []}

            elif number in folded:
                folded[number]["decisions"].append(entry)
                folded[number]["decision"] = entry["decision"]

        return folded

    def rule_unchanged(self) -> bool:

        return _sha256(self.directory / RULE) == self.config["ruleSha256"]


def load_campaign(name_or_path: str | Path, root: Path | None = None) -> Campaign:

    directory = Path(name_or_path)

    if not (directory / CAMPAIGN).exists():
        directory = Path(root or default_campaigns_root()) / str(name_or_path)

    if not (directory / CAMPAIGN).exists():
        raise SystemExit(f"no campaign at {directory}: cli iterate init --name ... first")

    entries = []
    ledger = directory / LEDGER

    if ledger.exists():
        for line in ledger.read_text(encoding="utf-8").splitlines():
            if line.strip():
                entries.append(json.loads(line))

    return Campaign(directory=directory, config=_read_json(directory / CAMPAIGN), entries=entries)


def active_campaigns(root: Path | None = None) -> list[str]:

    root = Path(root or default_campaigns_root())

    if not root.exists():
        return []

    return sorted(
        path.parent.name for path in root.glob(f"*/{CAMPAIGN}")
        if _read_json(path).get("status") == ACTIVE
    )


# ----------------------------------------------------------------------
# Git
# ----------------------------------------------------------------------


def _git(*args: str) -> str:

    result = subprocess.run(
        ["git", *args], capture_output=True, text=True, cwd=_repo_root(),
    )

    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {result.stderr.strip()}")

    return result.stdout.strip()


def _repo_root() -> Path:

    return Path(__file__).resolve().parents[3]


def head_commit() -> str:

    return _git("rev-parse", "HEAD")


def changed_paths(since: str) -> list[str]:
    """Files changed since `since`, committed or not, repo-relative."""

    committed = _git("diff", "--name-only", since, "HEAD").splitlines()
    uncommitted = _git("diff", "--name-only", "HEAD").splitlines()
    untracked = _git("ls-files", "--others", "--exclude-standard").splitlines()

    return sorted({path for path in committed + uncommitted + untracked if path})


def dirty_code() -> list[str]:
    """Uncommitted changes to code that can change a verdict."""

    uncommitted = _git("diff", "--name-only", "HEAD").splitlines()
    untracked = _git("ls-files", "--others", "--exclude-standard").splitlines()

    return sorted(path for path in uncommitted + untracked if path.startswith(CODE_PATHS))


# ----------------------------------------------------------------------
# Which tries a replay can measure
# ----------------------------------------------------------------------


def search_side_changes(evidence_thresholds: dict, thresholds: dict) -> list[str]:
    """
    The search-side fields on which `thresholds` (a full dump) differs from
    what the evidence run did. Non-empty means a replay of that run would
    not be this try.
    """

    changed = []

    for name in SEARCH_SIDE:

        before = evidence_thresholds.get(name)

        if before is None:
            before = _BEFORE_IT_EXISTED.get(name)

        if before is None:
            continue

        now = thresholds.get(name)

        if now is None:
            now = _BEFORE_IT_EXISTED.get(name)

        if now is None:
            continue

        if isinstance(before, list):
            before, now = sorted(before), sorted(now or [])

        if now != before:
            changed.append(name)

    fetched = evidence_thresholds.get("max_evidence_per_claim")

    if fetched is not None and thresholds.get("max_evidence_per_claim", fetched) > fetched:
        changed.append("max_evidence_per_claim (raised above what the evidence run fetched)")

    return changed


def search_side_code(paths: list[str]) -> list[str]:

    return [path for path in paths if path.startswith(SEARCH_SIDE_PATHS)]


# ----------------------------------------------------------------------
# init / propose
# ----------------------------------------------------------------------


def init_campaign(
    name: str,
    evidence_run: str | Path,
    *,
    model: str | None = None,
    thresholds_path: str | None = None,
    tries: int = DEFAULT_TRIES,
    screen: int = DEFAULT_SCREEN,
    target_median: float = TARGET_MEDIAN,
    target_p90: float = TARGET_P90,
    goal: str = "",
    root: Path | None = None,
) -> Campaign:

    directory = Path(root or default_campaigns_root()) / name

    if (directory / CAMPAIGN).exists():
        raise SystemExit(f"{directory} already exists: a campaign is started once")

    evidence = load_run(evidence_run)

    if not (evidence.directory / EVIDENCE).exists():
        raise SystemExit(f"{evidence.directory} keeps no {EVIDENCE}: only a full run since 2026-10-22 can be replayed")

    if evidence.manifest.get("mode", "full") != "full":
        raise SystemExit(f"{evidence.directory} is a {evidence.manifest.get('mode')} run, not a searched one")

    stem = evidence.dataset_stem

    if not stem.endswith("-train"):
        raise SystemExit(f"{evidence.directory} is over {stem}: a campaign works on the train half only")

    directory.mkdir(parents=True)

    (directory / RULE).write_text(RULE_TEXT, encoding="utf-8", newline="\n")

    sessions = evidence.manifest.get("sessions") or []

    campaign = Campaign(directory=directory, config={
        "name": name,
        "status": ACTIVE,
        "createdAt": _now(),
        "goal": goal,
        "ruleVersion": RULE_VERSION,
        "ruleSha256": _sha256(directory / RULE),
        "baseCommit": head_commit(),
        "dataset": {
            "path": (evidence.manifest.get("dataset") or {}).get("path", "").replace("\\", "/"),
            "stem": stem,
            "split": "train",
            "sha256": (evidence.manifest.get("dataset") or {}).get("sha256"),
            "rows": (evidence.manifest.get("dataset") or {}).get("rows"),
        },
        "evidence": {
            "run": str(evidence.directory).replace("\\", "/"),
            "key": evidence.key,
            "model": evidence.model,
            "thresholds": evidence.manifest.get("thresholds") or {},
            # The settings the evidence run ran under, so every try runs
            # under the same ones: concurrency and timeouts change seconds.
            "settings": (sessions[-1].get("settings") if sessions else None) or evidence.manifest.get("settings") or {},
        },
        "model": model or evidence.model,
        "thresholds": thresholds_path,
        "target": {"medianSeconds": target_median, "p90Seconds": target_p90},
        "budget": {"tries": tries},
        "screen": screen,
        "baseline": None,
        "searchedBaselines": [],
    })

    campaign.save()

    (directory / LEDGER).touch()

    return campaign


def try_label(campaign: Campaign, number: int) -> str:

    return f"iterate-{campaign.name}-{number:02d}"


def searched_baseline_label(campaign: Campaign, which: str) -> str:

    return f"iterate-{campaign.name}-searched-baseline-{which}"


def propose(
    campaign: Campaign,
    *,
    kind: str,
    hypothesis: str,
    prediction: str,
    thresholds_path: str | None = None,
    model: str | None = None,
    again: bool = False,
) -> dict:
    """Pre-register one try. Returns its ledger entry, with the commands to run it."""

    # Loaded here, not at import: cli.py imports this module.
    from src.evaluation.cli import load_thresholds

    if campaign.config["status"] != ACTIVE:
        raise SystemExit(f"campaign {campaign.name} is {campaign.config['status']}")

    if not campaign.rule_unchanged():
        raise SystemExit(f"{campaign.directory / RULE} changed after the campaign started: start a new campaign")

    if kind not in KINDS:
        raise SystemExit(f"--kind must be one of {', '.join(KINDS)}")

    tries = campaign.tries()

    if any(entry["decision"] is None for entry in tries.values()):
        pending = [number for number, entry in tries.items() if entry["decision"] is None]
        raise SystemExit(f"try {pending[0]} is not decided yet: score it (or `iterate abandon`) first")

    has_baseline = campaign.config.get("baseline") is not None

    if kind == "baseline":
        if has_baseline or tries:
            raise SystemExit("the baseline is try 0, and there is one")
    elif not has_baseline:
        raise SystemExit("the baseline first: iterate propose --kind baseline")

    number = 0 if kind == "baseline" else max(tries) + 1

    spent = sum(1 for n in tries if n > 0)

    if number > 0 and spent >= campaign.config["budget"]["tries"]:
        raise SystemExit(f"the campaign's {campaign.config['budget']['tries']} tries are spent: iterate close")

    thresholds_path = thresholds_path or (campaign.config.get("thresholds") if kind == "baseline" else None)

    thresholds = load_thresholds(thresholds_path)

    model = model or campaign.config["model"]

    dirty = dirty_code()

    if dirty and kind in ("prompt", "code", "search"):
        raise SystemExit(
            "commit the change first, so the commit each record carries is the code that ran: "
            + ", ".join(dirty[:5])
        )

    commit = head_commit()

    search_fields = search_side_changes(campaign.config["evidence"]["thresholds"], thresholds.model_dump(mode="json"))
    search_code = search_side_code(changed_paths(campaign.config["baseCommit"]))

    searched = kind == "search" or bool(search_fields) or bool(search_code)

    if kind == "baseline" and searched:
        raise SystemExit(
            "the baseline's thresholds differ from the evidence run on the search side "
            f"({', '.join(search_fields + search_code)}): a replay of it would not be them. "
            "Start the campaign from a searched run made with these thresholds."
        )

    identity = {"model": model, "thresholdsHash": thresholds_hash(thresholds), "commit": commit}

    if not again:
        for earlier in tries.values():
            # An abandoned or invalid try measured nothing: it may run again.
            if earlier["decision"] == INVALID:
                continue
            if {key: earlier.get(key) for key in identity} == identity:
                raise SystemExit(
                    f"try {earlier['try']} already ran this model, thresholds and commit; "
                    "the model is deterministic on fixed evidence (--again to insist)"
                )

    entry = {
        "event": "proposed",
        "try": number,
        "at": _now(),
        "kind": kind,
        "label": try_label(campaign, number),
        "hypothesis": hypothesis,
        "prediction": prediction,
        "thresholdsFile": thresholds_path,
        "thresholdsOverridden": thresholds.overridden_from_defaults(),
        "mode": "searched" if searched else "replay",
        "searchSide": search_fields + search_code,
        **identity,
    }

    campaign.append(entry)

    return entry


def run_command(campaign: Campaign, *, label: str, model: str, thresholds: str | None, replay: bool) -> str:
    """One `cli run`, from backend/, under the settings the evidence run ran under."""

    config = campaign.config

    env = " ".join(
        f"{name}={value}" for name, value in sorted((config["evidence"].get("settings") or {}).items())
        if value is not None
    )

    command = (
        f"{env} uv run python -m src.evaluation.cli run "
        f"--dataset {config['dataset']['path']} --split {config['dataset']['split']} "
        f"--model {model} --label {label}"
    )

    if thresholds:
        command += f" --thresholds {thresholds}"

    if replay:
        command += f" --replay {config['evidence']['run']}"

    return command.strip()


def commands(campaign: Campaign, entry: dict) -> list[str]:
    """The shell commands that run a try, from backend/: the screen, then the rest."""

    config = campaign.config

    lines = []

    replay = entry["mode"] == "replay"

    if not replay:

        made = {item["which"] for item in config.get("searchedBaselines") or []}

        for which in ("a", "b"):
            if which not in made:
                lines.append(
                    f"# searched baseline {which}: once per campaign, back to back with the try, "
                    "then `iterate searched-baseline --run <dir>`\n"
                    + run_command(
                        campaign, label=searched_baseline_label(campaign, which),
                        model=config["model"], thresholds=config.get("thresholds"), replay=False,
                    )
                )

    command = run_command(
        campaign, label=entry["label"], model=entry["model"], thresholds=entry.get("thresholdsFile"), replay=replay,
    )

    if entry["kind"] != "baseline" and config.get("screen"):
        lines.append(f"# the screen\n{command} --limit {config['screen']}")
        lines.append("# then, if `iterate score` says continue, the rest (the same run, resumed)\n" + command)
    else:
        lines.append(command)

    return lines


# ----------------------------------------------------------------------
# Measuring a try
# ----------------------------------------------------------------------


def claim_seconds(records: list[dict], evidence_records: dict[str, dict] | None) -> dict[str, float]:
    """
    Each ok record's seconds. Under a replay (evidence_records given), the
    replay's own seconds plus what retrieval took for that claim in the run
    replayed: the replay hands retrieval's answer over at once.
    """

    seconds = {}

    for record in records:

        latency = record.get("latency") or {}

        if record.get("status") != "ok" or latency.get("total") is None:
            continue

        total = latency["total"]

        if evidence_records is not None:
            original = (evidence_records.get(record["id"]) or {}).get("latency") or {}
            total = total - (latency.get("retrieval") or 0.0) + (original.get("retrieval") or 0.0)

        seconds[record["id"]] = total

    return seconds


def _spread(values: list[float]) -> dict:

    return {"median": rounded(median(values), 2), "p90": rounded(percentile(values, 90), 2), "n": len(values)}


@dataclass
class Pairing:
    """One try against one baseline, over the claims the try has run."""

    paired: int
    net: int
    accuracy: dict
    confidently_wrong: tuple[int, int]
    set_apart: tuple[int, int]
    seconds: tuple[dict, dict]

    def as_dict(self) -> dict:
        return {
            "paired": self.paired,
            "net": self.net,
            "accuracy": self.accuracy,
            "confidentlyWrong": {"baseline": self.confidently_wrong[0], "try": self.confidently_wrong[1]},
            "setApart": {"baseline": self.set_apart[0], "try": self.set_apart[1]},
            "seconds": {"baseline": self.seconds[0], "try": self.seconds[1]},
        }


def pair(baseline, candidate, comparison: dict, *, evidence_records=None, replay: bool) -> Pairing:

    a = {record["id"]: record for record in baseline.records}
    b = {record["id"]: record for record in candidate.records}

    shared = sorted(set(a) & set(b))

    scored = [
        key for key in shared
        if metrics.outcome(a[key]) == metrics.SCORED and metrics.outcome(b[key]) == metrics.SCORED
        and a[key]["label"] == b[key]["label"]
    ]

    set_apart = (
        sum(1 for key in shared if metrics.outcome(a[key]) != metrics.SCORED),
        sum(1 for key in shared if metrics.outcome(b[key]) != metrics.SCORED),
    )

    discordant = comparison["discordant"]

    evidence = evidence_records if replay else None

    seconds_a = claim_seconds([a[key] for key in shared], evidence if _is_replay(baseline) else None)
    seconds_b = claim_seconds([b[key] for key in shared], evidence)

    return Pairing(
        paired=len(scored),
        net=discordant["onlyB"] - discordant["onlyA"],
        accuracy=comparison["difference"]["accuracy"],
        confidently_wrong=(
            sum(1 for key in scored if confidently_wrong(a[key])),
            sum(1 for key in scored if confidently_wrong(b[key])),
        ),
        set_apart=set_apart,
        seconds=(_spread(list(seconds_a.values())), _spread(list(seconds_b.values()))),
    )


def _is_replay(run) -> bool:

    return run.manifest.get("mode") == "replay"


# ----------------------------------------------------------------------
# The rule
# ----------------------------------------------------------------------


def quality(pairing: Pairing) -> str:

    low = pairing.accuracy.get("low")
    cw_a, cw_b = pairing.confidently_wrong

    if low is not None and low > 0 and cw_b <= cw_a:
        return "better"

    if pairing.net <= WORSE_NET or cw_b > cw_a + WORSE_CONFIDENTLY_WRONG:
        return "worse"

    return "same"


def speed(pairing: Pairing, target: dict) -> dict:

    before, after = pairing.seconds

    meets = (
        after["median"] is not None and after["p90"] is not None
        and after["median"] <= target["medianSeconds"] and after["p90"] <= target["p90Seconds"]
    )

    faster = (
        after["median"] is not None and before["median"] is not None
        and after["median"] <= FASTER * before["median"]
    )

    return {"meetsTarget": meets, "faster": faster}


def decide(
    pairings: list[Pairing],
    *,
    target: dict,
    screening: bool,
    noise: int | None = None,
) -> tuple[str, list[str], str | None, dict | None]:
    """
    The rule in rule.md, as code. One pairing for a replayed try (against
    the baseline), two for a searched one (against each searched baseline,
    `noise` the gap between them in claims).
    """

    reasons = []

    for pairing in pairings:
        if pairing.set_apart[1] > pairing.set_apart[0] + SET_APART_SLACK:
            return INVALID, [
                f"sets apart {pairing.set_apart[1]} claims against the baseline's {pairing.set_apart[0]}: "
                "not checked or errors, which drop out of the comparison"
            ], None, None

    first = pairings[0]

    if screening:

        if all(p.net <= SCREEN_OUT_NET for p in pairings):
            return SCREENED_OUT, [f"{-first.net} more claims wrong, net, on the first {first.paired}"], None, None

        before, after = first.seconds

        if (
            after["median"] and before["median"]
            and after["median"] > SCREEN_OUT_SLOWER * before["median"] and first.net <= 0
        ):
            return SCREENED_OUT, [f"median {after['median']} s against {before['median']} s, and no claim gained"], None, None

        return CONTINUE, [f"net {first.net:+d} on the first {first.paired}: run the rest"], None, None

    verdicts = [quality(p) for p in pairings]

    if len(pairings) > 1:
        gap = noise or 0
        if all(v == "better" for v in verdicts) and min(p.net for p in pairings) > gap:
            judged = "better"
        elif all(v == "worse" for v in verdicts):
            judged = "worse"
        else:
            judged = "same"
        reasons.append(f"against the two searched baselines: {', '.join(verdicts)}; their own gap {gap} claims")
    else:
        judged = verdicts[0]

    pace = speed(first, target)

    acc = first.accuracy
    reasons.append(
        f"quality {judged}: accuracy {_pct(acc.get('a'))} -> {_pct(acc.get('b'))}, "
        f"{_points(acc.get('difference'))} [{_points(acc.get('low'))}, {_points(acc.get('high'))}], "
        f"net {first.net:+d} of {first.paired}; confidently wrong {first.confidently_wrong[0]} -> {first.confidently_wrong[1]}"
    )
    reasons.append(
        f"seconds a claim: median {first.seconds[0]['median']} -> {first.seconds[1]['median']}, "
        f"p90 {first.seconds[0]['p90']} -> {first.seconds[1]['p90']}"
        + ("; meets the target" if pace["meetsTarget"] else "")
        + ("; faster" if pace["faster"] else "")
    )

    if judged == "better":
        return KEEP, reasons, judged, pace

    cw_a, cw_b = first.confidently_wrong

    if (
        judged == "same" and first.net >= SAME_FOR_SPEED_NET and cw_b <= cw_a + WORSE_CONFIDENTLY_WRONG
        and (pace["faster"] or pace["meetsTarget"])
    ):
        return KEEP, reasons + ["kept for speed, at no detectable cost"], judged, pace

    return REJECT, reasons, judged, pace


def _pct(value) -> str:

    return "n/a" if value is None else f"{100 * value:.1f}%"


def _points(value) -> str:

    return "n/a" if value is None else f"{100 * value:+.1f}"


# ----------------------------------------------------------------------
# score
# ----------------------------------------------------------------------


def _check_run(campaign: Campaign, entry: dict, run, *, label: str, model: str, replay: bool) -> None:

    dataset = run.manifest.get("dataset") or {}

    problems = []

    if dataset.get("sha256") != campaign.config["dataset"]["sha256"] or run.dataset_stem != campaign.config["dataset"]["stem"]:
        problems.append(f"over {run.dataset_stem}, not the campaign's {campaign.config['dataset']['stem']}")

    if run.manifest.get("label") != label:
        problems.append(f"labelled {run.manifest.get('label')!r}, not {label!r}")

    if run.model != model:
        problems.append(f"run with {run.model}, not {model}")

    if replay:
        if run.manifest.get("mode") != "replay" or Path(str(run.manifest.get("replayOf") or "")).name != campaign.config["evidence"]["key"]:
            problems.append(f"not a replay of the evidence run {campaign.config['evidence']['key']}")
    elif run.manifest.get("mode", "full") != "full":
        problems.append(f"a {run.manifest.get('mode')} run, not a searched one")

    if entry.get("thresholdsHash") and run.manifest.get("thresholdsHash") != entry["thresholdsHash"]:
        problems.append(f"thresholds {run.manifest.get('thresholdsHash')}, not the proposed {entry['thresholdsHash']}")

    ran = str(run.manifest.get("gitCommit") or "unknown").split("-")[0]

    if entry.get("commit") and ran != "unknown" and ran != entry["commit"]:
        problems.append(f"code at {str(run.manifest.get('gitCommit'))[:12]}, not the proposed {entry['commit'][:12]}")

    if problems:
        raise SystemExit(f"{run.directory} is not try {entry['try']}: " + "; ".join(problems))


def register_searched_baseline(campaign: Campaign, run_directory: str | Path) -> dict:

    run = load_run(run_directory)

    which = next(
        (w for w in ("a", "b") if run.manifest.get("label") == searched_baseline_label(campaign, w)), None,
    )

    if which is None:
        raise SystemExit(f"{run.directory} is not labelled as a searched baseline of {campaign.name}")

    _check_run(
        campaign, {"try": f"searched baseline {which}"}, run,
        label=searched_baseline_label(campaign, which), model=campaign.config["model"], replay=False,
    )

    item = {"which": which, "run": str(run.directory).replace("\\", "/"), "key": run.key, "at": _now(), "records": len(run.records)}

    campaign.config["searchedBaselines"] = [
        existing for existing in campaign.config.get("searchedBaselines") or [] if existing["which"] != which
    ] + [item]

    campaign.save()

    return item


def score(campaign: Campaign, number: int, run_directory: str | Path, *, reports_root: Path | None = None) -> dict:

    if not campaign.rule_unchanged():
        raise SystemExit(f"{campaign.directory / RULE} changed after the campaign started: start a new campaign")

    tries = campaign.tries()

    if number not in tries:
        raise SystemExit(f"no try {number} in {campaign.name}")

    entry = tries[number]

    if entry["decision"] not in (None, CONTINUE):
        raise SystemExit(f"try {number} is decided: {entry['decision']}")

    replay = entry["mode"] == "replay"

    run = load_run(run_directory)

    _check_run(campaign, entry, run, label=entry["label"], model=entry["model"], replay=replay)

    rows = campaign.config["dataset"]["rows"]

    screening = entry["kind"] != "baseline" and len(run.records) < rows

    if entry["kind"] == "baseline":

        if len(run.records) < rows:
            raise SystemExit(f"the baseline has {len(run.records)} of {rows} claims: run it to the end")

        campaign.config["baseline"] = {"try": 0, "run": str(run.directory).replace("\\", "/"), "key": run.key}
        campaign.save()

        target = write_report(run.directory, root=reports_root)

        decision = {
            "event": "decided", "try": number, "at": _now(), "decision": REGISTERED,
            "run": campaign.config["baseline"]["run"], "report": str(target).replace("\\", "/"),
            "reasons": ["the campaign's baseline: every try is compared with it"],
            "seconds": _spread(list(claim_seconds(run.records, _evidence_records(campaign)).values())),
        }

        campaign.append(decision)

        return decision

    evidence_records = _evidence_records(campaign)

    if replay:
        baselines = [load_run(campaign.config["baseline"]["run"])]
    else:
        registered = sorted(campaign.config.get("searchedBaselines") or [], key=lambda item: item["which"])
        if len(registered) < 2:
            raise SystemExit("a searched try needs both searched baselines registered: iterate searched-baseline --run ...")
        baselines = [load_run(item["run"]) for item in registered]

    target_dir = write_report(run.directory, compare_with=baselines[0].directory, root=reports_root)

    comparisons = [_read_json(target_dir / "metrics.json")["comparison"]] + [
        compare(baseline, run) for baseline in baselines[1:]
    ]

    pairings = [
        pair(baseline, run, comparison, evidence_records=evidence_records, replay=replay)
        for baseline, comparison in zip(baselines, comparisons)
    ]

    noise = None

    if not replay:
        gap = compare(baselines[0], baselines[1])["discordant"]
        noise = abs(gap["onlyB"] - gap["onlyA"])

    verdict, reasons, judged, pace = decide(pairings, target=campaign.config["target"], screening=screening, noise=noise)

    decision = {
        "event": "decided",
        "try": number,
        "at": _now(),
        "decision": verdict,
        "screen": screening,
        "run": str(run.directory).replace("\\", "/"),
        "report": str(target_dir).replace("\\", "/"),
        "records": len(run.records),
        "reasons": reasons,
        "pairings": [p.as_dict() for p in pairings],
        "noise": noise,
        "changed": _changed_claims(baselines[0], run),
    }

    if judged is not None:
        decision["quality"] = judged
        decision["speed"] = pace

    campaign.append(decision)

    return decision


def _evidence_records(campaign: Campaign) -> dict[str, dict]:

    return {record["id"]: record for record in load_run(campaign.config["evidence"]["run"]).records}


def _changed_claims(baseline, candidate) -> dict:
    """The claims whose verdict changed, gained or lost: what the agent reads next."""

    a = {record["id"]: record for record in baseline.records}

    gained, lost, other = [], [], []

    for record in candidate.records:

        before = a.get(record["id"])

        if before is None or before.get("verdict") == record.get("verdict"):
            continue

        was_right = before.get("verdict") == before.get("label")
        is_right = record.get("verdict") == record.get("label")

        line = f"{record['id']} {before.get('verdict')} -> {record.get('verdict')} (gold {record.get('label')})"

        (gained if is_right and not was_right else lost if was_right and not is_right else other).append(line)

    return {"gained": gained, "lost": lost, "otherwise": other}


def abandon(campaign: Campaign, number: int, reason: str) -> dict:

    entry = campaign.tries().get(number)

    if entry is None or entry["decision"] not in (None, CONTINUE):
        raise SystemExit(f"try {number} is not pending")

    decision = {"event": "decided", "try": number, "at": _now(), "decision": INVALID, "reasons": [f"abandoned: {reason}"]}

    campaign.append(decision)

    return decision


# ----------------------------------------------------------------------
# status / close
# ----------------------------------------------------------------------


def find_run(campaign: Campaign, label: str, runs_root: Path | None = None) -> dict | None:
    """The run a try's label names, if it has started, and how far it got."""

    root = Path(runs_root or default_runs_root()) / campaign.config["dataset"]["stem"]

    for manifest in sorted(root.glob("*/*/run.json")):

        try:
            if _read_json(manifest).get("label") != label:
                continue
        except (OSError, ValueError):
            continue

        results = manifest.parent / "results.jsonl"
        lines = results.read_text(encoding="utf-8").count("\n") if results.exists() else 0

        return {"run": str(manifest.parent).replace("\\", "/"), "records": lines}

    return None


def best_kept(campaign: Campaign) -> dict | None:
    """The kept try a person would take to the test half: quality first, then the target, then seconds."""

    kept = [entry for entry in campaign.tries().values() if entry["decision"] == KEEP]

    if not kept:
        return None

    def rank(entry):
        last = entry["decisions"][-1]
        pairing = last["pairings"][0]
        return (
            last.get("quality") == "better",
            (last.get("speed") or {}).get("meetsTarget", False),
            pairing["net"],
            -(pairing["seconds"]["try"]["median"] or 1e9),
        )

    return max(kept, key=rank)


def status(campaign: Campaign, runs_root: Path | None = None) -> dict:

    tries = campaign.tries()

    spent = sum(1 for n in tries if n > 0)

    rows = []

    for number, entry in sorted(tries.items()):

        last = entry["decisions"][-1] if entry["decisions"] else None
        pairing = (last or {}).get("pairings", [None])[0] if last and last.get("pairings") else None

        row = {
            "try": number,
            "kind": entry["kind"],
            "mode": entry["mode"],
            "hypothesis": entry["hypothesis"],
            "decision": entry["decision"] or "pending",
            "net": pairing["net"] if pairing else None,
            "accuracy": pairing["accuracy"].get("b") if pairing else None,
            "confidentlyWrong": pairing["confidentlyWrong"]["try"] if pairing else None,
            "median": pairing["seconds"]["try"]["median"] if pairing else (last or {}).get("seconds", {}).get("median"),
            "p90": pairing["seconds"]["try"]["p90"] if pairing else (last or {}).get("seconds", {}).get("p90"),
        }

        if entry["decision"] in (None, CONTINUE):
            row["progress"] = find_run(campaign, entry["label"], runs_root)

        rows.append(row)

    best = best_kept(campaign)

    reached = bool(best and (best["decisions"][-1].get("speed") or {}).get("meetsTarget"))

    stop = None

    if campaign.config["status"] != ACTIVE:
        stop = f"the campaign is {campaign.config['status']}"
    elif not campaign.rule_unchanged():
        stop = "rule.md changed: the campaign cannot decide any more"
    elif reached:
        stop = f"try {best['try']} is kept and meets the target: close the campaign and report"
    elif spent >= campaign.config["budget"]["tries"] and not any(r["decision"] in ("pending", CONTINUE) for r in rows):
        stop = "the tries are spent: close the campaign and report"

    return {
        "campaign": campaign.name,
        "status": campaign.config["status"],
        "goal": campaign.config.get("goal"),
        "target": campaign.config["target"],
        "tries": {"spent": spent, "budget": campaign.config["budget"]["tries"]},
        "baseline": campaign.config.get("baseline"),
        "searchedBaselines": campaign.config.get("searchedBaselines"),
        "rows": rows,
        "best": best["try"] if best else None,
        "stop": stop,
    }


def render_status(state: dict) -> str:

    lines = [
        f"# Campaign {state['campaign']} ({state['status']})",
        "",
        f"Goal: {state['goal'] or '-'}",
        f"Target: median <= {state['target']['medianSeconds']:g} s, p90 <= {state['target']['p90Seconds']:g} s a claim",
        f"Tries: {state['tries']['spent']} of {state['tries']['budget']}",
        "",
        "| Try | Kind | Mode | Decision | Net | Accuracy | Conf. wrong | Median s | p90 s | Hypothesis |",
        "|---:|---|---|---|---:|---:|---:|---:|---:|---|",
    ]

    for row in state["rows"]:

        progress = row.get("progress")
        decision = row["decision"]

        if decision in ("pending", CONTINUE):
            decision += f" ({progress['records']} done)" if progress else " (not started)"

        cells = [
            str(row["try"]), row["kind"], row["mode"], decision,
            "" if row["net"] is None else f"{row['net']:+d}",
            "" if row["accuracy"] is None else _pct(row["accuracy"]),
            _blank(row["confidentlyWrong"]), _blank(row["median"]), _blank(row["p90"]),
            row["hypothesis"][:80].replace("|", "/"),
        ]

        lines.append("| " + " | ".join(cells) + " |")

    lines += ["", "Best kept: " + ("-" if state["best"] is None else f"try {state['best']}")]

    if state["stop"]:
        lines.append(f"STOP: {state['stop']}")

    return "\n".join(lines) + "\n"


def _blank(value) -> str:

    return "" if value is None else str(value)


def close(campaign: Campaign, reason: str) -> Path:
    """Ends the campaign and writes summary.md: every try, and what goes to the test half."""

    state = status(campaign)

    campaign.config["status"] = CLOSED
    campaign.config["closedAt"] = _now()
    campaign.config["closedBecause"] = reason
    campaign.save()

    tries = campaign.tries()

    lines = [render_status({**state, "status": CLOSED}), f"Closed: {reason}", ""]

    for number, entry in sorted(tries.items()):

        lines += [
            f"## Try {number}: {entry['kind']}, {entry['mode']} ({entry['decision'] or 'pending'})",
            "",
            f"- Hypothesis: {entry['hypothesis']}",
            f"- Predicted: {entry['prediction']}",
            f"- Thresholds: {json.dumps(entry.get('thresholdsOverridden') or {})}; model {entry['model']}; commit {entry['commit'][:12]}",
        ]

        for decision in entry["decisions"]:
            lines.append(f"- {decision['decision']}{' (screen)' if decision.get('screen') else ''}: " + "; ".join(decision.get("reasons") or []))
            changed = decision.get("changed") or {}
            for name in ("gained", "lost"):
                if changed.get(name):
                    lines.append(f"  - {name}: {', '.join(changed[name])}")

        lines.append("")

    best = best_kept(campaign)

    lines += [
        "## What goes to the test half",
        "",
        (
            f"Try {best['try']} ({best['label']}), once, run by the author: nothing here is a default "
            "until it holds there (the `fact-check-change` skill)."
            if best else "Nothing: no try was kept."
        ),
        "",
        "These are train-half figures on 69 claims, whose labels are mostly the AI pass's and unreviewed.",
    ]

    target = campaign.directory / "summary.md"

    target.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    return target
