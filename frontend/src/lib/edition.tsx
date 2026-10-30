"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

// The two editions the newsroom runs (backend src/config/editions.py,
// docs/decisions/editions.md). Chosen once, in the header, and read by
// every page that asks the backend for something the edition changes:
// the groups /discover offers, the run /Analyze starts, the voice a draft
// is written in, the reader's feed.
export type Edition = "positive" | "devastating";

export const EDITIONS: { id: Edition; name: string; short: string }[] = [
  { id: "positive", name: "Inspiring News", short: "Positive" },
  { id: "devastating", name: "Devastating News", short: "Devastating" },
];

export function editionName(edition: Edition): string {
  return EDITIONS.find((known) => known.id === edition)?.name ?? "Inspiring News";
}

/** What the tone gate measures in each edition, for labels. */
export function toneLabel(edition: Edition): string {
  return edition === "devastating" ? "Devastation" : "Positive impact";
}

const STORAGE_KEY = "inspiring-news.edition";

function stored(): Edition {
  // A convenience, not a record: private windows and blocked storage
  // throw or come back empty, and the page must still work.
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    return value === "devastating" ? "devastating" : "positive";
  } catch {
    return "positive";
  }
}

type EditionState = {
  edition: Edition;
  setEdition: (edition: Edition) => void;
  /** The stored choice has been read: before it, `edition` is only the default. */
  ready: boolean;
};

const EditionContext = createContext<EditionState>({
  edition: "positive",
  setEdition: () => {},
  ready: false,
});

/** A round's, a draft's or a run's edition; records from before the editions are positive. */
export function editionOf(record: { edition?: Edition | null } | null | undefined): Edition {
  return record?.edition === "devastating" ? "devastating" : "positive";
}

export function EditionProvider({ children }: { children: React.ReactNode }) {
  // "positive" on the server and the first client render, so the two
  // agree; the stored choice is read after hydration.
  const [edition, setState] = useState<Edition>("positive");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setState(stored());
    setReady(true);
  }, []);

  useEffect(() => {
    // The theme follows: globals.css redefines the accent under it.
    document.documentElement.dataset.edition = edition;
  }, [edition]);

  const setEdition = useCallback((next: Edition) => {
    setState(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Kept for this page only.
    }
  }, []);

  return <EditionContext.Provider value={{ edition, setEdition, ready }}>{children}</EditionContext.Provider>;
}

export function useEdition(): EditionState {
  return useContext(EditionContext);
}
