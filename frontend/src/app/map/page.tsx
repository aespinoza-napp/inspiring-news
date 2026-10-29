"use client";

import Link from "next/link";

import { MapView } from "@/components/map/MapView";
import { useNewsMap } from "@/lib/useNewsMap";
import styles from "@/components/map/MapPage.module.css";

// The readers' news map (docs/decisions/news-map.md): every published
// article as a point, the five sections as sectors of the disc, each
// topic a cluster in its section. Public, like /reader.
export default function NewsMapPage() {
  const { data, entities, error, loading } = useNewsMap();

  const header = (
    <>
      <h1>The news map</h1>
      <p className="subtitle">
        Every checked story as a point. Stories about the same topic sit together, the five sections around the
        circle. Click one to see what it is connected to.
      </p>
    </>
  );

  if (loading && !data) {
    return (
      <div className={styles.page}>
        {header}
        <p className={styles.muted}>Loading the map…</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className={styles.page}>
        {header}
        <p className="error-banner">{error ?? "The map could not be loaded."}</p>
      </div>
    );
  }

  if (data.count === 0) {
    return (
      <div className={styles.page}>
        {header}
        <p className="claims-note">
          No story has been published yet. The map fills as stories are checked and published; the{" "}
          <Link href="/reader">reader</Link> says how many have been analysed.
        </p>
      </div>
    );
  }

  return <MapView data={data} entities={entities} header={header} label={`The news map: ${data.count} stories`} />;
}
