"use client";

import Link from "next/link";
import { useState } from "react";

import { MapSearch } from "@/components/map/MapSearch";
import { VerdictBadge } from "@/components/VerdictBadge";
import { reasonText, type MapData, type MapLinks } from "@/lib/newsMap";
import { sameInterest, type Interest, type ReaderLists } from "@/lib/readerLists";
import type { Verdict } from "@/lib/types";
import styles from "./MapPage.module.css";

const VERDICTS = new Set(["TRUE", "PARTIALLY_TRUE", "MISLEADING", "UNVERIFIED", "FALSE"]);
const MAX_NOTE = 280;

interface Props {
  data: MapData;
  index: number;
  links: MapLinks | null;
  error: string | null;
  lists: ReaderLists;
  nameOf(kind: "article" | "entity", key: string): string;
  onSelect(id: string): void;
  onEntity(key: string): void;
  onClose(): void;
}

function FollowButton({ item, lists }: { item: Interest; lists: ReaderLists }) {
  const following = lists.interests.some((i) => sameInterest(i, item));

  return (
    <button
      type="button"
      className={`chip ${styles.chipButton} ${following ? styles.following : ""}`}
      aria-pressed={following}
      title={following ? `Stop following ${item.label}` : `Follow ${item.label}`}
      onClick={() => void (following ? lists.unfollow(item) : lists.follow(item))}
    >
      {following ? "✓ " : "+ "}
      {item.label}
    </button>
  );
}

export function ArticlePanel({ data, index, links, error, lists, nameOf, onSelect, onEntity, onClose }: Props) {
  const id = data.ids[index];
  const verdict = data.verdicts[index];
  const saved = lists.saved.some((s) => s.id === id);
  const mine = lists.connections.filter((c) => c.from === id || (c.toKind === "article" && c.to === id));

  const [connecting, setConnecting] = useState(false);
  const [target, setTarget] = useState<{ kind: "article" | "entity"; key: string } | null>(null);
  const [note, setNote] = useState("");

  return (
    <aside className={styles.panel} aria-label="The selected article">
      <button type="button" className={styles.close} onClick={onClose} aria-label="Close">
        ×
      </button>

      <h2 className={styles.panelTitle}>{data.titles[index]}</h2>
      <p className={styles.muted}>
        {data.sources[data.sourceOf[index]]}
        {data.days[index] ? ` · ${data.days[index]}` : ""}
      </p>
      <p>
        <VerdictBadge verdict={verdict && VERDICTS.has(verdict) ? (verdict as Verdict) : null} guide />
      </p>
      <p>
        <Link href={`/reader/${id}`}>Read the article and its checks →</Link>
      </p>

      {lists.signedIn ? (
        <div className={styles.toolbar}>
          <button type="button" className="button-secondary" aria-pressed={saved} onClick={() => void (saved ? lists.unsave(id) : lists.save(id))}>
            {saved ? "✓ Saved" : "Save"}
          </button>
          <button type="button" className="button-secondary" aria-expanded={connecting} onClick={() => setConnecting(!connecting)}>
            Connect to…
          </button>
        </div>
      ) : (
        <p className={styles.muted}>
          <Link href="/account">Sign in</Link> to save stories and draw your own connections.
        </p>
      )}

      {lists.error && <p className="error-banner">{lists.error}</p>}

      {connecting && (
        <div className={styles.connect}>
          {target ? (
            <p>
              To <strong>{nameOf(target.kind, target.key)}</strong>{" "}
              <button type="button" className={styles.linkButton} onClick={() => setTarget(null)}>
                (change)
              </button>
            </p>
          ) : (
            <MapSearch
              onArticle={(other) => other !== id && setTarget({ kind: "article", key: other })}
              onEntity={(key) => setTarget({ kind: "entity", key })}
            />
          )}
          <label className={styles.field}>
            <span>A note, for you (optional)</span>
            <textarea value={note} maxLength={MAX_NOTE} rows={2} onChange={(e) => setNote(e.target.value)} className={styles.searchInput} />
            <span className={styles.muted}>{MAX_NOTE - note.length} left</span>
          </label>
          <button
            type="button"
            disabled={!target}
            onClick={async () => {
              if (!target) return;
              await lists.connect(id, target.kind, target.key, note);
              setTarget(null);
              setNote("");
              setConnecting(false);
            }}
          >
            Connect
          </button>
        </div>
      )}

      {mine.length > 0 && (
        <>
          <p className="section-label">Your connections</p>
          <ul className={styles.related}>
            {mine.map((c) => {
              const other = c.from === id ? { kind: c.toKind, key: c.to } : { kind: "article" as const, key: c.from };
              return (
                <li key={c.id}>
                  {other.kind === "article" ? (
                    <button type="button" className={styles.linkButton} onClick={() => onSelect(other.key)}>
                      {nameOf("article", other.key)}
                    </button>
                  ) : (
                    <strong>{nameOf("entity", other.key)}</strong>
                  )}
                  {c.note && <span className={styles.muted}> · {c.note}</span>}{" "}
                  <button type="button" className={styles.linkButton} onClick={() => void lists.disconnect(c.id)} aria-label="Remove this connection">
                    remove
                  </button>
                </li>
              );
            })}
          </ul>
        </>
      )}

      {data.approximate[index] === "no_vector" && (
        <p className={styles.muted}>Placed by its topics alone: its text could not be compared with the others.</p>
      )}

      {error && <p className="error-banner">{error}</p>}
      {!links && !error && <p className={styles.muted}>Loading what it connects to…</p>}

      {links && (
        <>
          <p className="section-label">Topics</p>
          <div className="chip-row">
            {links.topics.map((topic) => (
              <FollowButton key={topic.key} item={{ kind: "topic", key: topic.key, label: topic.name }} lists={lists} />
            ))}
          </div>

          {links.entities.length > 0 && (
            <>
              <p className="section-label">Names in it</p>
              <div className="chip-row">
                {links.entities.map((entity) => (
                  <span key={entity.key} className={styles.entityChip}>
                    <button
                      type="button"
                      className={`chip ${styles.chipButton}`}
                      onClick={() => onEntity(entity.key)}
                      title={entity.articles > 1 ? `In ${entity.articles} stories: show them` : "Only in this story"}
                    >
                      {entity.name}
                      {entity.articles > 1 ? ` · ${entity.articles}` : ""}
                    </button>
                    <FollowButton item={{ kind: "entity", key: entity.key, label: entity.name }} lists={lists} />
                  </span>
                ))}
              </div>
            </>
          )}

          <p className="section-label">Related</p>
          {links.related.length === 0 ? (
            <p className={styles.muted}>Nothing published shares a claim, a source, a name or a topic with it yet.</p>
          ) : (
            <ol className={styles.related}>
              {links.related.map((related) => (
                <li key={related.id}>
                  <button type="button" className={styles.linkButton} onClick={() => onSelect(related.id)}>
                    {related.title}
                  </button>
                  <span className={styles.muted}>
                    {" "}
                    {related.via.slice(0, 2).map(reasonText).join("; ")}
                    {related.via.length > 2 ? `; and ${related.via.length - 2} more` : ""}
                  </span>
                </li>
              ))}
            </ol>
          )}
        </>
      )}
    </aside>
  );
}
