"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { readableDate } from "@/lib/reader";
import { StoryCard, StoryFeed, disclosureShort, storyLanguageName, storyPath } from "@/lib/stories";
import styles from "./StoryList.module.css";

const PAGE_SIZE = 4;

/**
 * The newsroom's own published articles, newest first, above the checked
 * news they were written from. Absent while nothing is published: an
 * empty "our articles" box would only say the newsroom has not started.
 *
 * Not tied to the feed's topic and language filters, which describe the
 * checked articles: a story's topic is its own, and it may be in Catalan,
 * which no checked article is.
 */
export function StoryList() {
  const [items, setItems] = useState<StoryCard[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    load(0)
      .then((feed) => {
        if (cancelled) return;
        setItems(feed.items);
        setTotal(feed.total);
      })
      .catch((exc) => {
        if (!cancelled) setError(exc instanceof Error ? exc.message : String(exc));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  async function more() {
    setLoading(true);
    try {
      const feed = await load(items.length);
      // By id: a story published meanwhile shifts the pages by one.
      setItems((current) => [...current, ...feed.items.filter((item) => !current.some((seen) => seen.id === item.id))]);
      setTotal(feed.total);
      setError(null);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setLoading(false);
    }
  }

  if (items.length === 0) {
    // Nothing published, or still loading: no section. A failure is
    // said quietly - the checked articles below still work.
    return error ? <p className="reader-fine">Our own articles could not be loaded: {error}</p> : null;
  }

  return (
    <section className={styles.section} aria-labelledby="stories-title">
      <h2 id="stories-title" className={styles.title}>
        From our newsroom
      </h2>
      <p className={styles.intro}>
        Articles we wrote from the checked news below and the fact-checks behind it. Each is written with AI and
        approved by a person, and links to every source it cites.
      </p>

      <div className={styles.cards}>
        {items.map((story) => (
          <StoryListCard key={story.id} story={story} />
        ))}
      </div>

      {error && <p className="reader-fine">{error}</p>}

      {items.length < total && (
        <button type="button" className="reader-pager-button" disabled={loading} onClick={more}>
          {loading ? "Loading…" : `Show more (${total - items.length})`}
        </button>
      )}
    </section>
  );
}

function StoryListCard({ story }: { story: StoryCard }) {
  const published = readableDate(story.publishedAt);
  const lead = story.subtitle || story.description;

  return (
    <article className={`card reader-card ${styles.card}`}>
      <p className="reader-byline">
        {published && <time dateTime={story.publishedAt}>{published}</time>}
        <span>{storyLanguageName(story.language)}</span>
        {story.topic && <span className="reader-topic">{story.topic}</span>}
      </p>

      <h3 className="reader-card-headline" lang={story.language}>
        <Link href={storyPath(story.id)}>{story.title}</Link>
      </h3>

      {lead && (
        <p className="reader-excerpt" lang={story.language}>
          {lead}
        </p>
      )}

      <p className={styles.disclosure}>{disclosureShort(story.disclosure)}</p>
    </article>
  );
}

async function load(offset: number): Promise<StoryFeed> {
  const search = new URLSearchParams({ offset: String(offset), limit: String(PAGE_SIZE) });
  const response = await fetch(`/api/reader/stories?${search}`, { cache: "no-store" });
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(
      typeof data?.detail === "string" ? data.detail : data?.error ?? `Loading our articles failed (${response.status}).`
    );
  }

  return data as StoryFeed;
}
