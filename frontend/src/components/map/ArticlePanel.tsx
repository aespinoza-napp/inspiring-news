"use client";

import Link from "next/link";

import { VerdictBadge } from "@/components/VerdictBadge";
import { reasonText, type MapData, type MapLinks } from "@/lib/newsMap";
import type { Verdict } from "@/lib/types";
import styles from "./MapPage.module.css";

const VERDICTS = new Set(["TRUE", "PARTIALLY_TRUE", "MISLEADING", "UNVERIFIED", "FALSE"]);

interface Props {
  data: MapData;
  index: number;
  links: MapLinks | null;
  error: string | null;
  onSelect(id: string): void;
  onEntity(key: string): void;
  onClose(): void;
}

export function ArticlePanel({ data, index, links, error, onSelect, onEntity, onClose }: Props) {
  const id = data.ids[index];
  const verdict = data.verdicts[index];

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
              <span className="chip" key={topic.key}>
                {topic.name}
              </span>
            ))}
          </div>

          {links.entities.length > 0 && (
            <>
              <p className="section-label">Names in it</p>
              <div className="chip-row">
                {links.entities.map((entity) => (
                  <button
                    type="button"
                    key={entity.key}
                    className={`chip ${styles.chipButton}`}
                    onClick={() => onEntity(entity.key)}
                    title={entity.articles > 1 ? `In ${entity.articles} articles: show them` : "Only in this article"}
                  >
                    {entity.name}
                    {entity.articles > 1 ? ` · ${entity.articles}` : ""}
                  </button>
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
