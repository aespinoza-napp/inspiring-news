import Link from "next/link";
import { LANG_SELF_NAME, READER_LANGS, ReaderLang, readerText } from "@/lib/readerText";

/**
 * Català · Español · English, each named in itself and marked with its
 * own `lang`, so a screen reader pronounces each name right whatever the
 * page is in. Buttons on the client pages (`onSelect`, which writes
 * `?lang=` with replaceState like the feed's filters); links on the
 * server-rendered story page (`hrefFor`), which has no handler to run.
 */
export function LanguageSwitch({
  lang,
  onSelect,
  hrefFor,
}: {
  lang: ReaderLang;
  onSelect?: (lang: ReaderLang) => void;
  hrefFor?: (lang: ReaderLang) => string;
}) {
  const t = readerText(lang);

  return (
    <nav className="reader-lang" aria-label={t.switchLabel}>
      {READER_LANGS.map((code) =>
        onSelect ? (
          <button
            key={code}
            type="button"
            className="reader-lang-option"
            lang={code}
            aria-pressed={code === lang}
            onClick={() => onSelect(code)}
          >
            {LANG_SELF_NAME[code]}
          </button>
        ) : (
          <Link
            key={code}
            href={hrefFor ? hrefFor(code) : `?lang=${code}`}
            className="reader-lang-option"
            lang={code}
            hrefLang={code}
            aria-current={code === lang ? "page" : undefined}
          >
            {LANG_SELF_NAME[code]}
          </Link>
        )
      )}
    </nav>
  );
}
