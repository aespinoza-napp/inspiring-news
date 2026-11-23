"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { MapView } from "@/components/map/MapView";
import { VerdictBadge } from "@/components/VerdictBadge";
import { NO_GROUP } from "@/lib/newsMap";
import { daysWithStories, isDay, madridToday, resolveDay, storiesBySection } from "@/lib/today";
import type { Verdict } from "@/lib/types";
import { useNewsMap } from "@/lib/useNewsMap";
import styles from "@/components/map/MapPage.module.css";

const VERDICTS = new Set(["TRUE", "PARTIALLY_TRUE", "MISLEADING", "UNVERIFIED", "FALSE"]);

function longDate(day: string): string {
  // Noon UTC, so no zone moves it to the day before or after.
  return new Date(`${day}T12:00:00Z`).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
}

// The day's news (docs/decisions/news-map.md): the map with the day's
// stories at full colour and the rest dimmed, then the day's stories by
// section. Public, like /reader.
export default function TodayPage() {
  const { data, entities, error, loading } = useNewsMap();
  const [asked, setAsked] = useState<string | null>(null);

  useEffect(() => {
    const day = new URLSearchParams(window.location.search).get("day");
    setAsked(isDay(day) ? day : madridToday());
  }, []);

  const go = (day: string) => {
    setAsked(day);
    const url = new URL(window.location.href);
    url.searchParams.set("day", day);
    url.searchParams.delete("a");
    window.history.replaceState(null, "", url);
  };

  const days = useMemo(() => (data ? daysWithStories(data) : []), [data]);
  const shown = useMemo(() => (asked ? resolveDay(asked, days) : null), [asked, days]);

  const emphasis = useMemo(() => {
    if (!data || !shown?.shown) return null;
    const set = new Set<number>();
    for (let i = 0; i < data.count; i++) if (data.days[i] === shown.shown) set.add(i);
    return set;
  }, [data, shown]);

  const sections = useMemo(() => (data && shown?.shown ? storiesBySection(data, shown.shown) : []), [data, shown]);

  const header = (
    <>
      <h1>{shown?.shown ? (shown.shown === madridToday() ? "Today's news" : `The news of ${longDate(shown.shown)}`) : "Today's news"}</h1>
      {shown?.fallback && shown.shown && (
        <p className="claims-note">
          Nothing was published on {longDate(shown.asked)}. Showing {longDate(shown.shown)}, the latest day before it with
          stories.
        </p>
      )}
      <nav className={styles.toolbar} aria-label="Days">
        <button type="button" className="button-secondary" disabled={!shown?.previous} onClick={() => shown?.previous && go(shown.previous)}>
          ← {shown?.previous ?? "Earlier"}
        </button>
        <button type="button" className="button-secondary" disabled={!shown?.next} onClick={() => shown?.next && go(shown.next)}>
          {shown?.next ?? "Later"} →
        </button>
        {shown?.shown && (
          <span className={styles.muted}>
            {emphasis?.size === 1 ? "1 story" : `${emphasis?.size ?? 0} stories`} on this day, the rest of the map dimmed
          </span>
        )}
      </nav>
    </>
  );

  if (loading || !asked) {
    return (
      <div className={styles.page}>
        <h1>Today&apos;s news</h1>
        <p className={styles.muted}>Loading…</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className={styles.page}>
        <h1>Today&apos;s news</h1>
        <p className="error-banner">{error ?? "The news could not be loaded."}</p>
      </div>
    );
  }

  if (!shown?.shown) {
    return (
      <div className={styles.page}>
        <h1>Today&apos;s news</h1>
        <p className="claims-note">
          No story has been published yet. The <Link href="/reader">reader</Link> says how many have been analysed.
        </p>
      </div>
    );
  }

  return (
    <>
      <MapView
        data={data}
        entities={entities}
        emphasis={emphasis}
        header={header}
        label={`The news map, with the ${emphasis?.size ?? 0} stories of ${shown.shown}`}
      />

      <section className={styles.page} aria-label="The day's stories by section">
        {sections.map(({ group, stories }) => (
          <div key={group} className={styles.daySection}>
            <h2 className={styles.dayHeading}>
              {group === NO_GROUP ? "Not placed in a section" : data.groups[group].name}{" "}
              <span className={styles.muted}>· {stories.length}</span>
            </h2>
            <ul className={styles.dayCards}>
              {stories.map((i) => (
                <li key={data.ids[i]} className={styles.dayCard}>
                  <Link href={`/reader/${data.ids[i]}`} className={styles.dayTitle}>
                    {data.titles[i]}
                  </Link>
                  <div className={styles.muted}>{data.sources[data.sourceOf[i]]}</div>
                  <VerdictBadge verdict={data.verdicts[i] && VERDICTS.has(data.verdicts[i]!) ? (data.verdicts[i] as Verdict) : null} guide />
                </li>
              ))}
            </ul>
          </div>
        ))}
      </section>
    </>
  );
}
