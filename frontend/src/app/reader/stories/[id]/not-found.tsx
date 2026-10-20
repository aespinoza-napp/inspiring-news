import Link from "next/link";
import { headers } from "next/headers";
import { pickLang, preferredLang, readerText, withLang } from "@/lib/readerText";

/**
 * What /reader/stories/<id> shows, with a 404, when nothing is published
 * there. A not-found page gets no search params, so its language is the
 * browser's (Accept-Language), else English.
 */
export default function StoryNotFound() {
  const lang = pickLang(preferredLang(headers().get("accept-language")));
  const t = readerText(lang);

  return (
    <div lang={lang}>
      <p className="reader-back">
        <Link href={withLang("/reader", lang)}>{t.backToFeed}</Link>
      </p>

      <div className="card reader-empty">
        <h1>{t.missingTitle}</h1>
        <p>
          {t.storyMissingText.before}
          <Link href={withLang("/reader", lang)}>{t.storyMissingText.link}</Link>
          {t.storyMissingText.after}
        </p>
      </div>
    </div>
  );
}
