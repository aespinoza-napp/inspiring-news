"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { MapSearch } from "@/components/map/MapSearch";
import { MapView } from "@/components/map/MapView";
import { accountCall, useAccount } from "@/lib/account";
import type { MapData } from "@/lib/newsMap";
import { sameInterest, useReaderLists, type Interest, type ReaderLists } from "@/lib/readerLists";
import { useNewsMap } from "@/lib/useNewsMap";
import styles from "@/components/map/MapPage.module.css";

// What For you's backend sends (backend src/services/news_map/for_you.py).
interface ForYouItem {
  id: string;
  title: string;
  source: string;
  day: string | null;
  score: number;
  parts: Record<"topic" | "entity" | "nearness" | "freshness", number>;
  mainPart: string;
  reasons: string[];
}

interface ForYouAnswer {
  weights: Record<string, number>;
  coldStart: boolean;
  considered: number;
  items: ForYouItem[];
}

interface Feed {
  hidden: string[];
  factors: Record<string, number>;
}

const MIN_CHOICES = 3;
const PART_LABELS: Record<string, string> = { topic: "your topics", entity: "your names", nearness: "near what you saved", freshness: "new" };

// Signed out, what a reader hid and lowered stays in this browser (and
// nowhere else), like their interests (lib/readerLists.ts).
const LOCAL_FEED = "inspiring-news:feed";

function readLocalFeed(): Feed {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(LOCAL_FEED) ?? "null");
    return parsed && Array.isArray(parsed.hidden) ? parsed : { hidden: [], factors: {} };
  } catch {
    return { hidden: [], factors: {} };
  }
}

function writeLocalFeed(feed: Feed): void {
  try {
    window.localStorage.setItem(LOCAL_FEED, JSON.stringify(feed));
  } catch {
    // Not kept beyond this visit.
  }
}

// The backend's src/services/news_map/for_you.py `lowered`, for a reader
// whose feed lives in their browser: 0.8 each time, never below 0.25.
function lowered(factors: Record<string, number>, part: string): Record<string, number> {
  return { ...factors, [part]: Math.max(0.25, (factors[part] ?? 1) * 0.8) };
}

export default function ForYouPage() {
  const account = useAccount();
  const lists = useReaderLists(Boolean(account.user), account.csrf, !account.loading);
  const { data, entities, error: mapError } = useNewsMap();
  const [editing, setEditing] = useState(false);

  if (!lists.ready || !data) {
    return (
      <div className={styles.page}>
        <h1>For you</h1>
        {mapError ? <p className="error-banner">{mapError}</p> : <p className={styles.muted}>Loading…</p>}
      </div>
    );
  }

  if (editing || lists.interests.length < MIN_CHOICES) {
    return <Chooser data={data} entities={entities} lists={lists} onDone={() => setEditing(false)} />;
  }

  return <Stories data={data} entities={entities} lists={lists} csrf={account.csrf} onEdit={() => setEditing(true)} />;
}

function Chooser({ data, entities, lists, onDone }: { data: MapData; entities: { k: string; n: string }[]; lists: ReaderLists; onDone(): void }) {
  const [chosen, setChosen] = useState<Interest[]>(lists.interests);

  const toggle = (item: Interest) =>
    setChosen((current) => (current.some((i) => sameInterest(i, item)) ? current.filter((i) => !sameInterest(i, item)) : [...current, item]));

  const isOn = (kind: Interest["kind"], key: string) => chosen.some((i) => sameInterest(i, { kind, key }));

  return (
    <div className={styles.page}>
      <h1>For you</h1>
      <p className="subtitle">
        Choose at least {MIN_CHOICES} things you would like to read about: sections, topics, or names you can search for.
        {lists.signedIn ? " They are kept in your account." : " They are kept in this browser; an account keeps them anywhere."}
      </p>

      {data.groups.map((group) => (
        <fieldset key={group.key} className={styles.chooserGroup}>
          <legend>
            <label>
              <input type="checkbox" checked={isOn("group", group.key)} onChange={() => toggle({ kind: "group", key: group.key, label: group.name })} /> {group.name}, all of it
            </label>
          </legend>
          <div className="chip-row">
            {data.topics
              .filter((topic) => topic.group === group.key)
              .map((topic) => (
                <button
                  key={topic.key}
                  type="button"
                  aria-pressed={isOn("topic", topic.key)}
                  className={`chip ${styles.chipButton} ${isOn("topic", topic.key) ? styles.following : ""}`}
                  onClick={() => toggle({ kind: "topic", key: topic.key, label: topic.name })}
                >
                  {isOn("topic", topic.key) ? "✓ " : ""}
                  {topic.name}
                </button>
              ))}
          </div>
        </fieldset>
      ))}

      <h2 className="section-label">Names</h2>
      <MapSearch
        onArticle={() => undefined}
        onEntity={(key) => {
          const name = entities.find((e) => e.k === key)?.n ?? data.entities.find((e) => e.k === key)?.n ?? key.split(":").slice(1).join(":");
          if (!isOn("entity", key)) toggle({ kind: "entity", key, label: name });
        }}
      />
      <div className="chip-row">
        {chosen.filter((i) => i.kind === "entity").map((i) => (
          <button key={i.key} type="button" className={`chip ${styles.chipButton} ${styles.following}`} onClick={() => toggle(i)} title="Remove">
            ✓ {i.label} ×
          </button>
        ))}
      </div>

      <div className={styles.toolbar}>
        <button
          type="button"
          disabled={chosen.length < MIN_CHOICES}
          onClick={async () => {
            await lists.setInterests(chosen);
            onDone();
          }}
        >
          Show my stories ({chosen.length} chosen)
        </button>
        {chosen.length < MIN_CHOICES && <span className={styles.muted}>{MIN_CHOICES - chosen.length} more to go.</span>}
      </div>
      {lists.error && <p className="error-banner">{lists.error}</p>}
    </div>
  );
}

function PartsBar({ item }: { item: ForYouItem }) {
  const parts = Object.entries(item.parts).filter(([, value]) => value > 0);

  return (
    <div className={styles.parts} title={parts.map(([part, value]) => `${PART_LABELS[part]}: ${value.toFixed(2)}`).join(", ")}>
      <div className={styles.partsBar} aria-hidden="true">
        {parts.map(([part, value], i) => (
          <span key={part} style={{ width: `${value * 100}%`, background: `var(--series-${i + 1})` }} />
        ))}
      </div>
      <span className={styles.muted}>
        {item.score.toFixed(2)} = {parts.map(([part, value]) => `${value.toFixed(2)} ${PART_LABELS[part]}`).join(" + ")}
      </span>
    </div>
  );
}

function Stories({ data, entities, lists, csrf, onEdit }: { data: MapData; entities: { k: string; n: string; t: string; c: number; x: number; y: number }[]; lists: ReaderLists; csrf: string | null; onEdit(): void }) {
  const [feed, setFeed] = useState<Feed | null>(null);
  const [answer, setAnswer] = useState<ForYouAnswer | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (lists.signedIn) {
      accountCall<Feed>("feed").then((value) => setFeed(value ?? { hidden: [], factors: {} })).catch((e: Error) => setError(e.message));
    } else {
      setFeed(readLocalFeed());
    }
  }, [lists.signedIn]);

  const load = useCallback(async () => {
    if (!feed) return;
    try {
      const response = await fetch("/api/map/for-you", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          interests: lists.interests.map(({ kind, key }) => ({ kind, key })),
          saved: lists.saved.map((s) => s.id),
          hidden: feed.hidden,
          factors: feed.factors,
          limit: 20,
        }),
      });
      if (!response.ok) throw new Error(response.status === 429 ? "Too many requests from here; try again shortly." : `Your stories could not be loaded (${response.status}).`);
      setAnswer(await response.json());
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [feed, lists.interests, lists.saved]);

  useEffect(() => {
    void load();
  }, [load]);

  const notInterested = async (item: ForYouItem) => {
    if (!feed) return;
    if (lists.signedIn) {
      try {
        setFeed(await accountCall<Feed>("not-interested", { body: { articleId: item.id, part: item.mainPart }, csrf }));
      } catch (e) {
        setError((e as Error).message);
      }
      return;
    }
    const next = { hidden: [...feed.hidden, item.id], factors: lowered(feed.factors, item.mainPart) };
    writeLocalFeed(next);
    setFeed(next);
  };

  const emphasis = useMemo(() => {
    if (!answer) return null;
    return new Set(answer.items.map((item) => data.indexOf.get(item.id)).filter((i): i is number => i !== undefined));
  }, [answer, data]);

  const header = (
    <>
      <h1>For you</h1>
      <p className="subtitle">
        Following {lists.interests.map((i) => i.label).join(", ")}.{" "}
        <button type="button" className={styles.linkButton} onClick={onEdit}>
          Change
        </button>
        {!lists.signedIn && (
          <>
            {" "}
            · <Link href="/account">An account</Link> keeps these anywhere.
          </>
        )}
      </p>
    </>
  );

  return (
    <>
      <div className={styles.page}>
        {header}
        {error && <p className="error-banner">{error}</p>}
        {!answer && !error && <p className={styles.muted}>Ranking the stories…</p>}
        {answer && answer.items.length === 0 && (
          <p className="claims-note">Nothing published fits these yet. Try more interests, or come back when more stories are out.</p>
        )}
        {answer && answer.items.length > 0 && (
          <ol className={styles.forYou}>
            {answer.items.map((item) => (
              <li key={item.id} className={styles.dayCard}>
                <Link href={`/reader/${item.id}`} className={styles.dayTitle}>
                  {item.title}
                </Link>
                <span className={styles.muted}>
                  {item.source}
                  {item.day ? ` · ${item.day}` : ""}
                </span>
                <span>Because {item.reasons.length ? item.reasons.join("; ") : "it is new"}.</span>
                <PartsBar item={item} />
                <div className={styles.toolbar}>
                  <Link href={`/map?a=${item.id}`} className="button-secondary">
                    On the map
                  </Link>
                  <button type="button" className="button-secondary" onClick={() => void notInterested(item)} title={`Hide it, and count ${PART_LABELS[item.mainPart] ?? item.mainPart} less for you`}>
                    Not interested
                  </button>
                </div>
              </li>
            ))}
          </ol>
        )}
        {answer && (
          <p className={styles.muted}>
            Scored as {Object.entries(answer.weights).map(([part, w]) => `${(w * 100).toFixed(0)}% ${PART_LABELS[part]}`).join(", ")}
            {" "}over {answer.considered} published stories. At most 7 of the first 10 from a topic you follow, 3 from any other, and one story an hour from an outlet.
          </p>
        )}
      </div>
      <MapView data={data} entities={entities} emphasis={emphasis} lists={lists} label="The news map, with your stories highlighted" />
    </>
  );
}
