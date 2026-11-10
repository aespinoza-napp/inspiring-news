"use client";

import { useCallback, useEffect, useState } from "react";
import { DraftStageProps } from "@/lib/drafts";
import { safeHref } from "@/lib/links";
import {
  ChannelPackage,
  PackageChannel,
  PackageChannelName,
  PackageList,
  PackageManifest,
  packageFileUrl,
  packageZipUrl,
  packagesApi,
} from "@/lib/packages";
import styles from "./PackagePanel.module.css";

const ALL: PackageChannelName[] = ["wordpress", "instagram", "stories", "tiktok"];

const LABELS: Record<PackageChannelName, string> = {
  wordpress: "WordPress",
  instagram: "Instagram carousel",
  stories: "Stories",
  tiktok: "TikTok",
};

/**
 * Ready-to-post packages (docs/decisions/writing.md, "Packages"): for an
 * approved or published draft, the WordPress post files, an Instagram
 * carousel, story frames and a TikTok photo post, each with what to do by
 * hand. WordPress can be sent to the site as a draft when its keys are set;
 * Instagram and TikTok are always posted by hand. Loaded once and after
 * each build or send; nothing here polls.
 */
export function PackagePanel({ draft }: DraftStageProps) {
  const [list, setList] = useState<PackageList | null>(null);
  const [chosen, setChosen] = useState<PackageChannelName[]>(ALL);
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const ready = draft.status === "approved" || draft.status === "published";

  const load = useCallback(async () => {
    try {
      setList(await packagesApi<PackageList>(draft.id));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }, [draft.id]);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const data = await packagesApi<PackageList>(draft.id);
        if (!cancelled) setList(data);
      } catch (exc) {
        if (!cancelled) setError(exc instanceof Error ? exc.message : String(exc));
      }
    })();

    return () => {
      cancelled = true;
    };
    // The text's hash changes with an edit, an approval or a publication:
    // read the list again so "made from an earlier text" stays true.
  }, [draft.id, draft.status, draft.updatedAt]);

  async function build() {
    setPending("build");
    setError(null);

    try {
      await packagesApi<PackageManifest>(draft.id, { method: "POST", body: { channels: chosen } });
      await load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setPending(null);
    }
  }

  async function send(manifest: PackageManifest) {
    const sure = window.confirm(
      "Send this post to the WordPress site as a draft? Nothing is public there until someone publishes it on the site."
    );
    if (!sure) return;

    setPending(`send-${manifest.id}`);
    setError(null);

    try {
      await packagesApi<PackageManifest>(`${draft.id}/${manifest.id}/wordpress`, { method: "POST", body: {} });
      await load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setPending(null);
    }
  }

  function toggle(name: PackageChannelName, on: boolean) {
    setChosen((current) => (on ? ALL.filter((item) => item === name || current.includes(item)) : current.filter((item) => item !== name)));
  }

  const channels = list?.channels ?? [];
  const canSend = channels.find((channel) => channel.name === "wordpress")?.canSend ?? false;

  return (
    <section className={`card ${styles.panel}`} aria-labelledby="packages-title">
      <h2 id="packages-title">Ready-to-post packages</h2>

      <p className={styles.help}>
        The article as files for each channel, saved with a manifest and downloadable as a zip. Instagram and TikTok
        are posted by hand: posting through their APIs needs a developer app each platform has approved, which there
        is not yet.
      </p>

      <fieldset className={styles.channels} disabled={!ready || pending !== null}>
        <legend className="section-label">Channels</legend>

        {ALL.map((name) => {
          const channel: PackageChannel | undefined = channels.find((item) => item.name === name);
          return (
            <div key={name} className={styles.channel}>
              <label className={styles.channelLabel}>
                <input type="checkbox" checked={chosen.includes(name)} onChange={(event) => toggle(name, event.target.checked)} />
                {channel?.label ?? LABELS[name]}
              </label>
              {channel?.note && <p className={styles.note}>{channel.note}</p>}
            </div>
          );
        })}

        <button type="button" disabled={!ready || pending !== null || chosen.length === 0} onClick={build}>
          {pending === "build" && <span className="spinner" aria-hidden="true" />}
          Build package
        </button>
        {!ready && <p className={styles.help}>Approve the draft first: a package is text about to be posted.</p>}
      </fieldset>

      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}

      {list && list.packages.length > 0 && (
        <ul className={styles.packages}>
          {list.packages.map((manifest) => (
            <Package
              key={manifest.id}
              manifest={manifest}
              stale={manifest.contentHash !== list.currentContentHash}
              canSend={canSend}
              sending={pending === `send-${manifest.id}`}
              blocked={pending !== null}
              onSend={() => send(manifest)}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

function Package({
  manifest,
  stale,
  canSend,
  sending,
  blocked,
  onSend,
}: {
  manifest: PackageManifest;
  stale: boolean;
  canSend: boolean;
  sending: boolean;
  blocked: boolean;
  onSend: () => void;
}) {
  return (
    <li className={styles.package}>
      <div className={styles.packageHead}>
        <span>
          {new Date(manifest.createdAt).toLocaleString()} · {manifest.files.length} files
          {stale && <span className={styles.stale}>Made from an earlier text</span>}
        </span>
        <a className="button-secondary" href={packageZipUrl(manifest)} download>
          Download zip
        </a>
      </div>

      {manifest.notes.length > 0 && (
        <ul className={styles.notes}>
          {manifest.notes.map((note, index) => (
            <li key={index}>{note}</li>
          ))}
        </ul>
      )}

      {manifest.channels.map((channel) => (
        <ChannelBlock
          key={channel.channel}
          manifest={manifest}
          channel={channel}
          canSend={canSend}
          sending={sending}
          blocked={blocked}
          onSend={onSend}
        />
      ))}
    </li>
  );
}

function ChannelBlock({
  manifest,
  channel,
  canSend,
  sending,
  blocked,
  onSend,
}: {
  manifest: PackageManifest;
  channel: ChannelPackage;
  canSend: boolean;
  sending: boolean;
  blocked: boolean;
  onSend: () => void;
}) {
  const [copied, setCopied] = useState(false);

  const images = channel.files.filter((path) => path.endsWith(".png"));
  const others = channel.files.filter((path) => !path.endsWith(".png"));
  const delivered = channel.delivery;

  async function copy() {
    if (!channel.caption) return;
    try {
      await navigator.clipboard.writeText(channel.caption);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className={styles.channelBlock}>
      <h3 className="section-label">{LABELS[channel.channel]}</h3>

      {images.length > 0 && (
        <div className={styles.thumbs}>
          {images.map((path) => (
            <a key={path} href={packageFileUrl(manifest, path)} target="_blank" rel="noopener">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={packageFileUrl(manifest, path)} alt={path} loading="lazy" />
            </a>
          ))}
        </div>
      )}

      {others.length > 0 && (
        <p className={styles.files}>
          {others.map((path) => (
            <a key={path} href={packageFileUrl(manifest, path)} target="_blank" rel="noopener">
              {path.split("/").pop()}
            </a>
          ))}
        </p>
      )}

      {channel.caption && (
        <details className={styles.caption}>
          <summary>
            Caption ({channel.caption.length} characters){" "}
            <button type="button" className="button-secondary" onClick={copy}>
              {copied ? "Copied" : "Copy"}
            </button>
          </summary>
          <pre>{channel.caption}</pre>
        </details>
      )}

      <ol className={styles.stepsList}>
        {channel.steps.map((step, index) => (
          <li key={index}>{step}</li>
        ))}
      </ol>

      {channel.channel === "wordpress" &&
        (delivered ? (
          <p className={styles.delivered}>
            Sent as draft post {delivered.postId} on {new Date(delivered.sentAt).toLocaleString()}
            {safeHref(delivered.link) && (
              <>
                {" · "}
                <a href={safeHref(delivered.link)!} target="_blank" rel="noopener">
                  Open it on the site
                </a>
              </>
            )}
          </p>
        ) : (
          canSend && (
            <button type="button" disabled={blocked} onClick={onSend}>
              {sending && <span className="spinner" aria-hidden="true" />}
              Send to WordPress as a draft
            </button>
          )
        ))}
    </div>
  );
}
