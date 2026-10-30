"use client";

import { EDITIONS, editionName, useEdition } from "@/lib/edition";

// The header's brand and the Positive / Devastating choice. Everything
// the edition changes reads it from lib/edition.tsx.
export function EditionSwitch() {
  const { edition, setEdition } = useEdition();

  return (
    <div className="edition-switch">
      <span className="brand">{editionName(edition)} Tools</span>
      <div className="edition-toggle" role="radiogroup" aria-label="Edition">
        {EDITIONS.map((option) => (
          <button
            key={option.id}
            type="button"
            role="radio"
            aria-checked={edition === option.id}
            className={edition === option.id ? "edition-option is-active" : "edition-option"}
            onClick={() => setEdition(option.id)}
          >
            {option.short}
          </button>
        ))}
      </div>
    </div>
  );
}
