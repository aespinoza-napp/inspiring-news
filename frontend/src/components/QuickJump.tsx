"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { traceHref } from "@/lib/trace";

/**
 * The header's "go to": paste any URL or id a page shows and land on
 * its journey (app/trace/page.tsx). "/" focuses it from anywhere, as on
 * most sites with a search box - unless the person is already typing.
 *
 * Hidden on the public reader (components/NavLinks.tsx's PUBLIC): /trace is
 * behind the site password.
 */
export function QuickJump() {
  const router = useRouter();
  const pathname = usePathname();
  const [value, setValue] = useState("");
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key !== "/" || event.metaKey || event.ctrlKey || event.altKey) return;

      const target = event.target as HTMLElement | null;
      const typing =
        target &&
        (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.tagName === "SELECT" || target.isContentEditable);

      if (typing) return;

      event.preventDefault();
      input.current?.focus();
    }

    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // The public reader's visitors have no password for /trace.
  if (pathname === "/reader" || pathname.startsWith("/reader/")) return null;

  return (
    <form
      className="quick-jump"
      role="search"
      onSubmit={(event) => {
        event.preventDefault();
        const q = value.trim();
        if (!q) return;
        setValue("");
        input.current?.blur();
        router.push(traceHref(q));
      }}
    >
      <input
        ref={input}
        type="text"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="Trace a URL or id…  /"
        aria-label="Trace an article: paste its URL, a job id, a draft id or a reader id"
        autoComplete="off"
        spellCheck={false}
      />
    </form>
  );
}
