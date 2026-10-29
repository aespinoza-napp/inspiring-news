// The day's news (docs/goals.md, N4): which day, which stories, how many
// per section. A day is Madrid's, as the backend dates each article
// (backend/src/services/news_map/days.py).

import { NO_GROUP, type MapData } from "@/lib/newsMap";

const DAY = /^\d{4}-\d{2}-\d{2}$/;

// Today in Madrid, YYYY-MM-DD, whatever the reader's own zone.
export function madridToday(now: Date = new Date()): string {
  // en-CA formats as YYYY-MM-DD.
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Madrid", year: "numeric", month: "2-digit", day: "2-digit" }).format(now);
}

export function isDay(value: string | null): value is string {
  return value !== null && DAY.test(value);
}

// Every day with at least one published story, newest first.
export function daysWithStories(data: MapData): string[] {
  return Array.from(new Set(data.days.filter((day): day is string => Boolean(day)))).sort().reverse();
}

export interface ShownDay {
  // The day asked for, and the one shown: the same unless the first had
  // no story, when it is the latest earlier day that has one (else the
  // latest day of all).
  asked: string;
  shown: string | null;
  fallback: boolean;
  previous: string | null;
  next: string | null;
}

export function resolveDay(asked: string, days: string[]): ShownDay {
  const shown = days.includes(asked) ? asked : days.find((day) => day < asked) ?? days[0] ?? null;
  const index = shown ? days.indexOf(shown) : -1;

  return {
    asked,
    shown,
    fallback: shown !== asked,
    // `days` runs newest first: the previous day is the next one in it.
    previous: index >= 0 && index + 1 < days.length ? days[index + 1] : null,
    next: index > 0 ? days[index - 1] : null,
  };
}

// The day's stories, by section in the map's order, each section's list
// newest first as the map holds them. A story no topic placed is its own
// last section.
export function storiesBySection(data: MapData, day: string): { group: number; stories: number[] }[] {
  const sections = new Map<number, number[]>();

  for (let i = 0; i < data.count; i++) {
    if (data.days[i] !== day) continue;
    const group = data.group[i];
    const list = sections.get(group);
    if (list) list.push(i);
    else sections.set(group, [i]);
  }

  return Array.from(sections.entries())
    .sort(([a], [b]) => (a === NO_GROUP ? 1 : b === NO_GROUP ? -1 : a - b))
    .map(([group, stories]) => ({ group, stories }));
}
