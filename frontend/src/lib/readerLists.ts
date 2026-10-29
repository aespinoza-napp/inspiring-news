"use client";

import { useCallback, useEffect, useState } from "react";

import { accountCall } from "@/lib/account";

// What a reader follows, saves and connects (backend
// src/services/accounts/reader_data.py). Signed in, kept by the server;
// signed out, the interests alone are kept in this browser, and offered
// for import when the reader makes an account.

export type InterestKind = "group" | "topic" | "entity";

export interface Interest {
  kind: InterestKind;
  key: string;
  label: string;
}

export interface SavedStory {
  id: string;
  title: string;
}

export interface Connection {
  id: number;
  from: string;
  toKind: "article" | "entity";
  to: string;
  note: string;
}

const LOCAL_KEY = "inspiring-news:interests";

// Browser storage can be missing or refuse (a private window, blocked
// site data): the page must work without it.
export function readLocalInterests(): Interest[] {
  try {
    const raw = window.localStorage.getItem(LOCAL_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((i) => i && typeof i.key === "string" && typeof i.kind === "string") : [];
  } catch {
    return [];
  }
}

export function writeLocalInterests(items: Interest[]): void {
  try {
    if (items.length) window.localStorage.setItem(LOCAL_KEY, JSON.stringify(items));
    else window.localStorage.removeItem(LOCAL_KEY);
  } catch {
    // Not kept: the choice still applies to this visit.
  }
}

export function sameInterest(a: { kind: string; key: string }, b: { kind: string; key: string }): boolean {
  return a.kind === b.kind && a.key === b.key;
}

export interface ReaderLists {
  signedIn: boolean;
  ready: boolean;
  interests: Interest[];
  saved: SavedStory[];
  connections: Connection[];
  error: string | null;
  follow(item: Interest): Promise<void>;
  unfollow(item: Interest): Promise<void>;
  setInterests(items: Interest[]): Promise<void>;
  save(id: string): Promise<void>;
  unsave(id: string): Promise<void>;
  connect(from: string, toKind: "article" | "entity", to: string, note: string): Promise<void>;
  disconnect(id: number): Promise<void>;
}

export function useReaderLists(signedIn: boolean, csrf: string | null, accountReady: boolean): ReaderLists {
  const [interests, setInterestsState] = useState<Interest[]>([]);
  const [saved, setSaved] = useState<SavedStory[]>([]);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!accountReady) return;
    let cancelled = false;

    if (!signedIn) {
      setInterestsState(readLocalInterests());
      setSaved([]);
      setConnections([]);
      setReady(true);
      return;
    }

    Promise.all([
      accountCall<{ items: Interest[] }>("interests"),
      accountCall<{ items: SavedStory[] }>("saved"),
      accountCall<{ items: Connection[] }>("connections"),
    ])
      .then(([i, s, c]) => {
        if (cancelled) return;
        setInterestsState(i?.items ?? []);
        setSaved(s?.items ?? []);
        setConnections(c?.items ?? []);
        setReady(true);
      })
      .catch((e: Error) => !cancelled && setError(e.message));

    return () => {
      cancelled = true;
    };
  }, [signedIn, accountReady]);

  const attempt = useCallback(async (action: () => Promise<void>) => {
    setError(null);
    try {
      await action();
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  const setInterests = useCallback(
    (items: Interest[]) =>
      attempt(async () => {
        if (!signedIn) {
          writeLocalInterests(items);
          setInterestsState(items);
          return;
        }
        const answer = await accountCall<{ items: Interest[] }>("interests/set", { body: { items: items.map(({ kind, key }) => ({ kind, key })) }, csrf });
        setInterestsState(answer?.items ?? []);
      }),
    [attempt, signedIn, csrf],
  );

  const follow = useCallback(
    (item: Interest) =>
      attempt(async () => {
        if (!signedIn) {
          const next = [...readLocalInterests().filter((i) => !sameInterest(i, item)), item];
          writeLocalInterests(next);
          setInterestsState(next);
          return;
        }
        const answer = await accountCall<{ items: Interest[] }>("interests/follow", { body: { kind: item.kind, key: item.key }, csrf });
        setInterestsState(answer?.items ?? []);
      }),
    [attempt, signedIn, csrf],
  );

  const unfollow = useCallback(
    (item: Interest) =>
      attempt(async () => {
        if (!signedIn) {
          const next = readLocalInterests().filter((i) => !sameInterest(i, item));
          writeLocalInterests(next);
          setInterestsState(next);
          return;
        }
        const answer = await accountCall<{ items: Interest[] }>("interests/unfollow", { body: { kind: item.kind, key: item.key }, csrf });
        setInterestsState(answer?.items ?? []);
      }),
    [attempt, signedIn, csrf],
  );

  const save = useCallback(
    (id: string) => attempt(async () => setSaved((await accountCall<{ items: SavedStory[] }>("saved/add", { body: { articleId: id }, csrf }))?.items ?? [])),
    [attempt, csrf],
  );

  const unsave = useCallback(
    (id: string) => attempt(async () => setSaved((await accountCall<{ items: SavedStory[] }>("saved/remove", { body: { articleId: id }, csrf }))?.items ?? [])),
    [attempt, csrf],
  );

  const connect = useCallback(
    (from: string, toKind: "article" | "entity", to: string, note: string) =>
      attempt(async () =>
        setConnections((await accountCall<{ items: Connection[] }>("connections/add", { body: { fromArticle: from, toKind, to, note }, csrf }))?.items ?? []),
      ),
    [attempt, csrf],
  );

  const disconnect = useCallback(
    (id: number) => attempt(async () => setConnections((await accountCall<{ items: Connection[] }>("connections/remove", { body: { id }, csrf }))?.items ?? [])),
    [attempt, csrf],
  );

  return { signedIn, ready, interests, saved, connections, error, follow, unfollow, setInterests, save, unsave, connect, disconnect };
}
