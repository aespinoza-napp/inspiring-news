"use client";

import { useEffect, useState } from "react";

import { decode, type MapData, type MapDocument, type MapEntitiesDocument } from "@/lib/newsMap";

export interface NewsMapState {
  data: MapData | null;
  entities: MapEntitiesDocument["entities"];
  error: string | null;
  loading: boolean;
}

// The whole map (or one day of it) and the entities named by more than
// one article. The browser revalidates both through the backend's ETag
// (the proxy relays it, Cache-Control: no-cache), so a revisit with
// nothing new published is two 304s.
export function useNewsMap(day: string | null = null): NewsMapState {
  const [state, setState] = useState<NewsMapState>({ data: null, entities: [], error: null, loading: true });

  useEffect(() => {
    let cancelled = false;
    const query = day ? `?day=${encodeURIComponent(day)}` : "";

    setState((previous) => ({ ...previous, loading: true, error: null }));

    Promise.all([
      fetch(`/api/map/articles${query}`, { cache: "no-cache" }).then(async (response) => {
        if (!response.ok) throw new Error((await response.json().catch(() => null))?.error ?? `The map could not be loaded (${response.status}).`);
        return (await response.json()) as MapDocument;
      }),
      fetch("/api/map/entities", { cache: "no-cache" })
        .then((response) => (response.ok ? (response.json() as Promise<MapEntitiesDocument>) : null))
        .catch(() => null),
    ])
      .then(([document, entities]) => {
        if (cancelled) return;
        setState({ data: decode(document), entities: entities?.entities ?? [], error: null, loading: false });
      })
      .catch((error: Error) => {
        if (cancelled) return;
        setState({ data: null, entities: [], error: error.message, loading: false });
      });

    return () => {
      cancelled = true;
    };
  }, [day]);

  return state;
}
