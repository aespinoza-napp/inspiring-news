"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BlindFact,
  CustomFact,
  CustomFactInput,
  DatasetOverview,
  DatasetReviewQueue,
  Verdict,
} from "@/lib/types";

// The labelling tool for the custom evaluation set. Every field maps to a
// key of the stored row (x-fact's keys plus the guide's own), and the
// rules the backend enforces are the guide's tie-break rules - see
// docs/final_document/sections/custom_dataset.tex.

const GROUP_NAMES: Record<string, string> = {
  society: "Society",
  science: "Science",
  environment: "Environment",
  culture: "Culture",
  health: "Health",
};

const TIER_NAMES: Record<string, string> = {
  primary: "Primary (report, official statistic, study)",
  reference_media: "Reference media",
  press_release: "Press release",
  social_media: "Social media",
};

const EMPTY: CustomFactInput = {
  claim: "",
  language: "en",
  site: null,
  claimant: null,
  claimDate: "",
  label: "TRUE",
  referenceEvidenceLinks: [],
  topic: "",
  claimType: "factual",
  sourceTier: "primary",
  onlyOwnSource: false,
  evidenceDate: null,
  articleUrl: null,
  annotatorNote: null,
};

// Kept after a save: an article usually yields several claims, and these
// are the article's, not the claim's.
const STICKY: (keyof CustomFactInput)[] = ["language", "site", "claimant", "claimDate", "articleUrl", "topic"];

export default function DatasetPage() {
  const [tab, setTab] = useState<"label" | "review">("label");
  const [overview, setOverview] = useState<DatasetOverview | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const response = await fetch("/api/dataset", { cache: "no-store" });
      const data = await response.json();
      if (!response.ok) throw new Error(errorText(data, response.status));
      setOverview(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load the dataset.");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <>
      <h1>Dataset</h1>
      <p className="subtitle">
        Hand-labelled claims for the custom evaluation set: the same row format
        as the x-fact file, plus the topic, so both are scored by the same
        harness. Aim for {overview?.schema.targets.total ?? 150} facts, balanced
        across verdicts and topic groups; about 20% are then labelled a second
        time, blind.
      </p>

      <div className="dataset-tabs" role="tablist">
        <button role="tab" aria-selected={tab === "label"} className={tab === "label" ? "is-active" : ""} onClick={() => setTab("label")}>
          Label facts
        </button>
        <button role="tab" aria-selected={tab === "review"} className={tab === "review" ? "is-active" : ""} onClick={() => setTab("review")}>
          Review 20%
        </button>
      </div>

      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}

      {overview && tab === "label" && <LabelTab overview={overview} reload={load} />}
      {overview && tab === "review" && <ReviewTab overview={overview} reload={load} />}
    </>
  );
}

// ---------------------------------------------------------------------
// Label tab
// ---------------------------------------------------------------------

function LabelTab({ overview, reload }: { overview: DatasetOverview; reload: () => Promise<void> }) {
  const { schema, summary, facts } = overview;

  const [form, setForm] = useState<CustomFactInput>(EMPTY);
  const [links, setLinks] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  function set<K extends keyof CustomFactInput>(key: K, value: CustomFactInput[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function startEdit(fact: CustomFact) {
    // Only the input's own keys: the stored row's id, dates and review are
    // the server's to set.
    const input = { ...EMPTY };
    for (const key of Object.keys(EMPTY) as (keyof CustomFactInput)[]) {
      (input as Record<string, unknown>)[key] = fact[key];
    }
    setForm(input);
    setLinks(fact.referenceEvidenceLinks.join("\n"));
    setEditing(fact.id);
    setMessage(null);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function reset(keepArticle: boolean) {
    setForm((current) => {
      if (!keepArticle) return EMPTY;
      const next = { ...EMPTY };
      for (const key of STICKY) (next as Record<string, unknown>)[key] = current[key];
      return next;
    });
    setLinks("");
    setEditing(null);
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setMessage(null);

    const body: CustomFactInput = {
      ...form,
      referenceEvidenceLinks: links.split(/\s+/).map((l) => l.trim()).filter(Boolean),
      site: blankToNull(form.site),
      claimant: blankToNull(form.claimant),
      articleUrl: blankToNull(form.articleUrl),
      annotatorNote: blankToNull(form.annotatorNote),
      evidenceDate: blankToNull(form.evidenceDate),
    };

    try {
      const response = await fetch(editing ? `/api/dataset/${editing}` : "/api/dataset", {
        method: editing ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(errorText(data, response.status));

      setMessage({ ok: true, text: editing ? "Fact updated." : "Fact saved. The article's fields are kept for its next claim." });
      reset(!editing);
      await reload();
    } catch (err) {
      setMessage({ ok: false, text: err instanceof Error ? err.message : "Could not save." });
    } finally {
      setSaving(false);
    }
  }

  async function remove(fact: CustomFact) {
    if (!window.confirm(`Delete this fact?\n\n${fact.claim}`)) return;
    const response = await fetch(`/api/dataset/${fact.id}`, { method: "DELETE" });
    if (!response.ok && response.status !== 204) {
      setMessage({ ok: false, text: `Could not delete (${response.status}).` });
      return;
    }
    if (editing === fact.id) reset(false);
    await reload();
  }

  const topicsByGroup = useMemo(() => {
    const grouped: Record<string, typeof schema.topics> = {};
    for (const topic of schema.topics) (grouped[topic.group] ??= []).push(topic);
    return grouped;
  }, [schema.topics]);

  const topicName = (id: string) => schema.topics.find((t) => t.id === id)?.name ?? id;

  return (
    <>
      <BalanceCard overview={overview} />

      <form className="card dataset-form" onSubmit={submit}>
        <h2>{editing ? "Edit fact" : "New fact"}</h2>

        <label className="field-label" htmlFor="ds-claim">Claim *</label>
        <textarea
          id="ds-claim"
          required
          value={form.claim}
          onChange={(e) => set("claim", e.target.value)}
          placeholder="One checkable assertion, as the article states it."
          style={{ minHeight: "4.5rem" }}
        />

        <div className="dataset-grid">
          <Field label="Verdict *" id="ds-label">
            <select id="ds-label" value={form.label} onChange={(e) => set("label", e.target.value as Verdict)}>
              {schema.labels.map((l) => (
                <option key={l.label} value={l.label}>
                  {l.label} — {l.labelRaw}
                </option>
              ))}
            </select>
            <small>{schema.labels.find((l) => l.label === form.label)?.description}</small>
          </Field>

          <Field label="Topic *" id="ds-topic">
            <select id="ds-topic" required value={form.topic} onChange={(e) => set("topic", e.target.value)}>
              <option value="">Choose…</option>
              {schema.groups.map((group) => (
                <optgroup key={group} label={GROUP_NAMES[group] ?? group}>
                  {(topicsByGroup[group] ?? []).map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name} ({summary.byTopic[t.id] ?? 0})
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </Field>

          <Field label="Claim type *" id="ds-type">
            <select id="ds-type" value={form.claimType} onChange={(e) => set("claimType", e.target.value as CustomFactInput["claimType"])}>
              {schema.claimTypes.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </Field>

          <Field label="Language *" id="ds-lang">
            <select id="ds-lang" value={form.language} onChange={(e) => set("language", e.target.value as "en" | "es")}>
              <option value="en">en</option>
              <option value="es">es</option>
            </select>
          </Field>

          <Field label="Article URL" id="ds-article">
            <input id="ds-article" type="text" value={form.articleUrl ?? ""} onChange={(e) => set("articleUrl", e.target.value)} placeholder="https://…" />
          </Field>

          <Field label="Site (outlet)" id="ds-site">
            <input id="ds-site" type="text" value={form.site ?? ""} onChange={(e) => set("site", e.target.value)} placeholder="Taken from the URL if empty" />
          </Field>

          <Field label="Claimant" id="ds-claimant">
            <input id="ds-claimant" type="text" value={form.claimant ?? ""} onChange={(e) => set("claimant", e.target.value)} placeholder="Who asserts it (person, NGO, outlet)" />
          </Field>

          <Field label="Claim date (article published) *" id="ds-date">
            <input id="ds-date" type="date" required value={form.claimDate} onChange={(e) => set("claimDate", e.target.value)} />
          </Field>
        </div>

        <label className="field-label" htmlFor="ds-links">Evidence links (one per line)</label>
        <textarea
          id="ds-links"
          value={links}
          onChange={(e) => setLinks(e.target.value)}
          placeholder={"https://…\nRequired unless the verdict is UNVERIFIED."}
          style={{ minHeight: "4.5rem" }}
        />

        <div className="dataset-grid">
          <Field label="Strongest source *" id="ds-tier">
            <select id="ds-tier" value={form.sourceTier} onChange={(e) => set("sourceTier", e.target.value as CustomFactInput["sourceTier"])}>
              {schema.sourceTiers.map((s) => (
                <option key={s} value={s}>{TIER_NAMES[s] ?? s}</option>
              ))}
            </select>
          </Field>

          <Field label="Newest evidence dated" id="ds-evdate">
            <input id="ds-evdate" type="date" value={form.evidenceDate ?? ""} onChange={(e) => set("evidenceDate", e.target.value)} />
            <small>Must not be after the claim date.</small>
          </Field>
        </div>

        <label className="checkbox-label">
          <input type="checkbox" checked={form.onlyOwnSource} onChange={(e) => set("onlyOwnSource", e.target.checked)} />
          Only the organisation the story is about backs this (its own release or report) → UNVERIFIED, name it in the note
        </label>

        <label className="field-label" htmlFor="ds-note" style={{ marginTop: "1rem" }}>Annotator note</label>
        <textarea
          id="ds-note"
          value={form.annotatorNote ?? ""}
          onChange={(e) => set("annotatorNote", e.target.value)}
          placeholder="Why this verdict; which rule decided a close call."
          style={{ minHeight: "3.5rem" }}
        />

        <div className="form-row">
          <button type="submit" disabled={saving}>
            {saving && <span className="spinner" aria-hidden="true" />}
            {editing ? "Save changes" : "Save fact"}
          </button>
          {editing && (
            <button type="button" className="dataset-secondary" onClick={() => reset(false)}>
              Cancel edit
            </button>
          )}
        </div>

        {message && (
          <div className={message.ok ? "dataset-ok" : "error-banner"} role={message.ok ? "status" : "alert"}>
            {message.text}
          </div>
        )}
      </form>

      <GuideCard />

      <div className="card">
        <h2>Facts ({facts.length})</h2>
        {facts.length === 0 ? (
          <p className="stats-muted">Nothing labelled yet.</p>
        ) : (
          <div className="stats-table-wrap dataset-table">
            <table className="stats-table">
              <thead>
                <tr>
                  <th>Claim</th>
                  <th>Verdict</th>
                  <th>Topic</th>
                  <th>Lang</th>
                  <th>Date</th>
                  <th className="stats-number">Links</th>
                  <th>Review</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {facts.map((fact) => (
                  <tr key={fact.id}>
                    <td>
                      {fact.claim}
                      <div className="stats-muted">{fact.site}{fact.claimant ? ` · ${fact.claimant}` : ""}</div>
                    </td>
                    <td><span className={`badge badge-${fact.label.toLowerCase()}`}>{fact.label}</span></td>
                    <td>{topicName(fact.topic)}</td>
                    <td>{fact.language}</td>
                    <td>{fact.claimDate}</td>
                    <td className="stats-number">{fact.referenceEvidenceLinks.length}</td>
                    <td>{fact.review ? (fact.review.agrees ? "agrees" : `→ ${fact.review.label}`) : "—"}</td>
                    <td className="dataset-actions">
                      <button type="button" className="dataset-secondary" onClick={() => startEdit(fact)}>Edit</button>
                      <button type="button" className="dataset-secondary" onClick={() => remove(fact)}>Delete</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}

function BalanceCard({ overview }: { overview: DatasetOverview }) {
  const { schema, summary } = overview;
  const { targets } = schema;
  const labels = schema.labels.map((l) => l.label);

  return (
    <div className="card">
      <h2>Balance</h2>
      <p className="stats-muted">
        {summary.total} of {targets.total} facts (at least {targets.minimum}). Each cell aims at{" "}
        {targets.perCell}; a short cell is reported short, not padded.
        {" "}en {summary.byLanguage.en ?? 0} · es {summary.byLanguage.es ?? 0} ·{" "}
        {Object.entries(summary.byClaimType).map(([k, v]) => `${k} ${v}`).join(" · ")}
      </p>

      <div className="dataset-progress" aria-hidden="true">
        <div style={{ width: `${Math.min(100, (summary.total / targets.total) * 100)}%` }} />
        <span style={{ left: `${(targets.minimum / targets.total) * 100}%` }} />
      </div>

      <div className="stats-table-wrap dataset-table">
        <table className="stats-table dataset-matrix">
          <thead>
            <tr>
              <th>Verdict</th>
              {schema.groups.map((g) => <th key={g} className="stats-number">{GROUP_NAMES[g] ?? g}</th>)}
              <th className="stats-number">Total / {targets.perLabel}</th>
            </tr>
          </thead>
          <tbody>
            {labels.map((label) => (
              <tr key={label}>
                <td><span className={`badge badge-${label.toLowerCase()}`}>{label}</span></td>
                {schema.groups.map((g) => {
                  const n = summary.matrix[label]?.[g] ?? 0;
                  return (
                    <td key={g} className={`stats-number ${n >= targets.perCell ? "dataset-cell-full" : n > 0 ? "dataset-cell-some" : ""}`}>
                      {n}
                    </td>
                  );
                })}
                <td className="stats-number"><b>{summary.byLabel[label] ?? 0}</b></td>
              </tr>
            ))}
            <tr>
              <td><b>Total / {targets.perGroup}</b></td>
              {schema.groups.map((g) => <td key={g} className="stats-number"><b>{summary.byGroup[g] ?? 0}</b></td>)}
              <td className="stats-number"><b>{summary.total}</b></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

function GuideCard() {
  return (
    <details className="card dataset-guide">
      <summary><b>Tie-break rules</b> — decide close calls the same way every time</summary>
      <ol>
        <li><b>The organisation's own source.</b> If only the NGO's or company's own release, report or post backs the claim, it is UNVERIFIED (not enough evidence). Tick the box and name the source in the note.</li>
        <li><b>Numeric tolerance.</b> A figure within ±10% relative of the source (30% against 28%), or a reasonable rounding of it, is supported. Beyond that the claim is PARTIALLY_TRUE if the rest holds, FALSE if the figure is the claim.</li>
        <li><b>Date of the evidence.</b> Only evidence available on the article's publication date. Something confirmed later does not change the verdict.</li>
        <li><b>Source hierarchy.</b> Primary source (report, official statistic, study) &gt; reference media &gt; press release &gt; social media. Record the strongest one used.</li>
      </ol>
    </details>
  );
}

// ---------------------------------------------------------------------
// Review tab
// ---------------------------------------------------------------------

function ReviewTab({ overview, reload }: { overview: DatasetOverview; reload: () => Promise<void> }) {
  const [queue, setQueue] = useState<DatasetReviewQueue | null>(null);
  const [label, setLabel] = useState<Verdict | "">("");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);

  const loadQueue = useCallback(async () => {
    const response = await fetch("/api/dataset/review", { cache: "no-store" });
    const data = await response.json();
    if (!response.ok) {
      setError(errorText(data, response.status));
      return;
    }
    setQueue(data);
  }, []);

  useEffect(() => {
    loadQueue();
  }, [loadQueue]);

  const next: BlindFact | undefined = queue?.sample.find((f) => !f.review);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!next || !label) return;

    const response = await fetch(`/api/dataset/${next.id}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ label, note: note.trim() || null }),
    });
    const data = await response.json();
    if (!response.ok) {
      setError(errorText(data, response.status));
      return;
    }
    setLabel("");
    setNote("");
    setError(null);
    await Promise.all([loadQueue(), reload()]);
  }

  if (!queue) return error ? <div className="error-banner">{error}</div> : null;

  const { agreement } = queue;
  const done = queue.sample.filter((f) => f.review).length;
  const topicName = (id: string) => overview.schema.topics.find((t) => t.id === id)?.name ?? id;

  return (
    <>
      <div className="card">
        <h2>Self-agreement</h2>
        <p className="stats-muted">
          {done} of {queue.sampleSize} sampled facts reviewed ({Math.round(overview.schema.targets.reviewShare * 100)}% of{" "}
          {overview.summary.total}, chosen by a hash of their id, not by hand). Label each one again
          without looking at the first answer — ideally a week after labelling it.
        </p>
        <div className="stats-totals">
          <Stat label="Observed agreement" value={agreement.observed === null ? "—" : `${Math.round(agreement.observed * 100)}%`} />
          <Stat label="Cohen's kappa" value={agreement.kappa === null ? "—" : agreement.kappa.toFixed(2)} />
          <Stat label="Disagreements" value={String(agreement.disagreements.length)} />
        </div>
      </div>

      {error && <div className="error-banner" role="alert">{error}</div>}

      {next ? (
        <form className="card dataset-form" onSubmit={submit}>
          <h2>Blind review</h2>
          <p className="dataset-claim">{next.claim}</p>
          <p className="stats-muted">
            {next.site}{next.claimant ? ` · ${next.claimant}` : ""} · {next.language} · published {next.claimDate} ·{" "}
            {topicName(next.topic)} · {next.claimType}
            {next.evidenceDate ? ` · evidence up to ${next.evidenceDate}` : ""}
          </p>
          {next.articleUrl && safeHref(next.articleUrl) && (
            <p><a href={safeHref(next.articleUrl)} target="_blank" rel="noreferrer">Article</a></p>
          )}
          {next.referenceEvidenceLinks.length > 0 && (
            <ul>
              {next.referenceEvidenceLinks.map((link) =>
                safeHref(link) ? (
                  <li key={link}><a href={safeHref(link)} target="_blank" rel="noreferrer">{link}</a></li>
                ) : null,
              )}
            </ul>
          )}

          <div className="dataset-grid">
            <Field label="Your verdict *" id="rv-label">
              <select id="rv-label" required value={label} onChange={(e) => setLabel(e.target.value as Verdict)}>
                <option value="">Choose…</option>
                {overview.schema.labels.map((l) => (
                  <option key={l.label} value={l.label}>{l.label} — {l.labelRaw}</option>
                ))}
              </select>
            </Field>
            <Field label="Note" id="rv-note">
              <input id="rv-note" type="text" value={note} onChange={(e) => setNote(e.target.value)} />
            </Field>
          </div>
          <button type="submit" disabled={!label}>Save review</button>
        </form>
      ) : (
        <div className="card">
          <p className="stats-muted">
            {queue.sampleSize === 0 ? "Nothing to review yet." : "Every sampled fact is reviewed."}
          </p>
        </div>
      )}

      {agreement.disagreements.length > 0 && (
        <div className="card">
          <h2>Disagreements</h2>
          <p className="stats-muted">
            Settle each against the guide, then correct the fact on the Label tab if the first
            label was wrong. Agreement stays measured on the first label.
          </p>
          <ul>
            {agreement.disagreements.map((d) => (
              <li key={d.id}>
                {d.claim} — <b>{d.firstLabel}</b> then <b>{d.secondLabel}</b>
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
}

// ---------------------------------------------------------------------
// Bits
// ---------------------------------------------------------------------

function Field({ label, id, children }: { label: string; id: string; children: React.ReactNode }) {
  return (
    <div className="dataset-field">
      <label className="field-label" htmlFor={id}>{label}</label>
      {children}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="stats-total">
      <div className="stats-total-value">{value}</div>
      <div className="stats-total-label">{label}</div>
    </div>
  );
}

function blankToNull(value: string | null): string | null {
  return value && value.trim() ? value.trim() : null;
}

// Evidence links are typed in by hand; only http(s) become links, as on
// the Live screen.
function safeHref(url: string): string | undefined {
  return /^https?:\/\//i.test(url) ? url : undefined;
}

// FastAPI's 422 detail is a list of {loc, msg}; the proxy's is {error}.
function errorText(data: unknown, status: number): string {
  const body = data as { detail?: unknown; error?: string } | null;
  if (body?.error) return body.error;
  if (Array.isArray(body?.detail)) {
    return body.detail
      .map((d: { msg?: string; loc?: unknown[] }) => {
        const field = d.loc?.filter((p) => p !== "body").join(".");
        const msg = (d.msg ?? "").replace(/^Value error, /, "");
        return field ? `${field}: ${msg}` : msg;
      })
      .join(" · ");
  }
  if (typeof body?.detail === "string") return body.detail;
  return `Request failed (${status})`;
}
