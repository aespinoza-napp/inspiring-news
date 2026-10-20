"use client";

import { useEffect, useState } from "react";
import { ReaderLang, pickLang, preferredLang, readerLang } from "@/lib/readerText";

/**
 * The language of a client-rendered reader page: `?lang=` when the reader
 * chose one, else `contentLang` (the article's own), else the browser's,
 * else English (lib/readerText.ts). Read once on arrival and written on
 * every choice - in the handler, not an effect, for the Strict Mode reason
 * in app/graph/page.tsx.
 *
 * The root layout's <html lang="en"> serves the operator pages too, so
 * the page sets it while it is open and puts it back when it leaves.
 */
export function useReaderLang(contentLang?: string | null): [ReaderLang, (lang: ReaderLang) => void] {
  const [chosen, setChosen] = useState<ReaderLang | null>(null);
  const [browser, setBrowser] = useState<string | null>(null);

  useEffect(() => {
    setChosen(readerLang(new URLSearchParams(window.location.search).get("lang")));
    setBrowser(preferredLang(window.navigator.languages ?? [window.navigator.language]));
  }, []);

  const lang = pickLang(chosen, contentLang, browser);

  useEffect(() => {
    const root = document.documentElement;
    const before = root.lang;
    root.lang = lang;
    return () => {
      root.lang = before;
    };
  }, [lang]);

  function choose(next: ReaderLang) {
    setChosen(next);
    const url = new URL(window.location.href);
    url.searchParams.set("lang", next);
    window.history.replaceState(null, "", url);
  }

  return [lang, choose];
}
