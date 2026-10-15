import Link from "next/link";

/** What /reader/stories/<id> shows, with a 404, when nothing is published there. */
export default function StoryNotFound() {
  return (
    <>
      <p className="reader-back">
        <Link href="/reader">← Checked articles</Link>
      </p>

      <div className="card reader-empty">
        <h1>No published article here</h1>
        <p>
          Either nothing was published under this link, or the article has been taken down. Our articles are
          listed on the <Link href="/reader">reader</Link>.
        </p>
      </div>
    </>
  );
}
