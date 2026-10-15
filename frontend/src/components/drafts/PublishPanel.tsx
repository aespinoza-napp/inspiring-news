"use client";

import { useEffect, useState } from "react";
import { ArticleDraft, DraftStageProps, DraftStatus, PublishRecord, draftsApi } from "@/lib/drafts";
import { safeHref } from "@/lib/links";
import styles from "./PublishPanel.module.css";

/** GET /publishing/channels (backend src/api/publish_routes.py). */
interface Channel {
  name: string;
  label: string;
  available: boolean;
  /** Why it cannot publish; null when it can. */
  reason: string | null;
}

// Shown until the channel list arrives, or if it cannot be had: the web
// is the one channel that publishes, and the backend checks every
// channel it is sent anyway.
const WEB_ONLY: Channel[] = [{ name: "web", label: "Web", available: true, reason: null }];

type Action = "approve" | "publish" | "unpublish";

const STEPS: { status: DraftStatus; label: string }[] = [
  { status: "draft", label: "Draft" },
  { status: "approved", label: "Approved" },
  { status: "published", label: "Published" },
];

/**
 * Approving and publishing the draft, per channel
 * (docs/decisions/writing.md, "Publishing"). Approve marks the text as it
 * stands as ready; Publish puts that text on the chosen channels; Unpublish
 * takes it down and leaves it approved. A person's edit sends an approved
 * draft back to draft, and a published one cannot be edited until it is
 * unpublished. Every action is refused while a step runs on the draft.
 */
export function PublishPanel({ draft, onChange }: DraftStageProps) {
  const [channels, setChannels] = useState<Channel[] | null>(null);
  const [channelsError, setChannelsError] = useState<string | null>(null);
  const [chosen, setChosen] = useState<string[]>(["web"]);
  const [pending, setPending] = useState<Action | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const response = await fetch("/api/publishing/channels", { cache: "no-store" });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(
            typeof data?.detail === "string" ? data.detail : data?.error ?? `Loading the channels failed (${response.status}).`
          );
        }
        if (!cancelled) setChannels(data as Channel[]);
      } catch (exc) {
        if (!cancelled) setChannelsError(exc instanceof Error ? exc.message : String(exc));
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  const shown = channels ?? WEB_ONLY;
  const selected = chosen.filter((name) => shown.some((channel) => channel.name === name && channel.available));

  const status = draft.status;
  const blocked = draft.busy !== null || pending !== null;

  async function act(action: Action, body?: unknown) {
    setPending(action);
    setError(null);

    try {
      onChange(await draftsApi<ArticleDraft>(`${draft.id}/${action}`, { method: "POST", body }));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setPending(null);
    }
  }

  function toggle(name: string, on: boolean) {
    setChosen((current) => (on ? [...current.filter((item) => item !== name), name] : current.filter((item) => item !== name)));
  }

  function unpublish() {
    const sure = window.confirm(
      "Take this article down? Its public page stops answering at once. The text stays approved, so it can be published again as it is."
    );
    if (sure) act("unpublish");
  }

  return (
    <section className={`card ${styles.panel}`} aria-labelledby="publish-title">
      <h2 id="publish-title">Publish</h2>

      <ol className={styles.steps} aria-label="Status">
        {STEPS.map((step) => (
          <li key={step.status} className={step.status === status ? styles.current : undefined} aria-current={step.status === status ? "step" : undefined}>
            {step.label}
          </li>
        ))}
      </ol>

      {/* A warning, not a block: the person may know the text is fine. */}
      {status !== "published" && draft.review === null && (
        <p className={styles.warning} role="note">
          This text has not been reviewed: the corrector has not checked it as it stands now (a review is cleared
          whenever the text changes). You can still approve and publish it.
        </p>
      )}

      {status === "draft" && (
        <div className={styles.step}>
          <p className={styles.help}>
            Approve the text as it stands to publish it. Editing it afterwards sends it back to draft.
          </p>
          <button type="button" disabled={blocked} onClick={() => act("approve")}>
            {pending === "approve" && <span className="spinner" aria-hidden="true" />}
            Approve
          </button>
        </div>
      )}

      {status !== "published" && (
        <fieldset className={styles.channels} disabled={status !== "approved" || blocked}>
          <legend className="section-label">Channels</legend>

          {shown.map((channel) => (
            <div key={channel.name} className={styles.channel}>
              <label className={styles.channelLabel}>
                <input
                  type="checkbox"
                  checked={channel.available && chosen.includes(channel.name)}
                  disabled={!channel.available}
                  onChange={(event) => toggle(channel.name, event.target.checked)}
                />
                {channel.label}
                {!channel.available && <span className={styles.unavailable}>Not available yet</span>}
              </label>
              {!channel.available && channel.reason && <p className={styles.reason}>{channel.reason}</p>}
            </div>
          ))}

          {channelsError && <p className={styles.reason}>The channel list could not be loaded ({channelsError}).</p>}

          <button
            type="button"
            disabled={status !== "approved" || blocked || selected.length === 0}
            onClick={() => act("publish", { channels: selected })}
          >
            {pending === "publish" && <span className="spinner" aria-hidden="true" />}
            Publish
          </button>
          {status === "draft" && <p className={styles.help}>Approve the draft first.</p>}
        </fieldset>
      )}

      {draft.published.length > 0 && (
        <div className={styles.records}>
          <h3 className="section-label">Published</h3>
          <ul>
            {draft.published.map((record, index) => (
              <Record key={index} record={record} label={shown.find((channel) => channel.name === record.channel)?.label} />
            ))}
          </ul>
        </div>
      )}

      {status === "published" && (
        <div className={styles.step}>
          <button type="button" className="button-secondary" disabled={blocked} onClick={unpublish}>
            {pending === "unpublish" && <span className="spinner" aria-hidden="true" />}
            Unpublish
          </button>
          <p className={styles.help}>
            To change a published article, unpublish it, edit it, approve it and publish it again. Its address stays
            the same; the public page shows the text as it was when it was published.
          </p>
        </div>
      )}

      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}
    </section>
  );
}

function Record({ record, label }: { record: PublishRecord; label: string | undefined }) {
  // The backend gives a path on this site for the web; any other
  // address must be http(s) to become a link.
  const href = record.url && /^\/(?!\/)/.test(record.url) ? record.url : safeHref(record.url);

  return (
    <li className={styles.record}>
      <span className={styles.recordChannel}>{label ?? record.channel}</span>
      <time dateTime={record.at}>{new Date(record.at).toLocaleString()}</time>
      {href ? (
        <a href={href} target="_blank" rel="noopener noreferrer">
          Open the public page
        </a>
      ) : (
        record.url && <span>{record.url}</span>
      )}
    </li>
  );
}
