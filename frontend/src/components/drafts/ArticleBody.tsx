import { Fragment, ReactNode } from "react";

/**
 * A draft's or a published article's body: the small Markdown the writer
 * produces (paragraphs, `##`/`###` headings, `- ` lists, **bold**) with
 * `[n]` citations linked to `#source-n` - the id every source list on the
 * draft and the public page gives its n-th source (1-based).
 *
 * Built as React elements, never as HTML: the text is a model's output,
 * and the public reader shows it to anyone. No Markdown dependency for
 * four constructs.
 */
export function ArticleBody({ body }: { body: string }) {
  const blocks = body.replace(/\r\n/g, "\n").split(/\n{2,}/).map((block) => block.trim()).filter(Boolean);

  return (
    <div className="article-body">
      {blocks.map((block, index) => {
        const lines = block.split("\n");

        if (block.startsWith("### ")) return <h3 key={index}>{inline(block.slice(4))}</h3>;
        if (block.startsWith("## ")) return <h2 key={index}>{inline(block.slice(3))}</h2>;

        if (lines.every((line) => /^[-*] /.test(line))) {
          return (
            <ul key={index}>
              {lines.map((line, item) => (
                <li key={item}>{inline(line.slice(2))}</li>
              ))}
            </ul>
          );
        }

        return <p key={index}>{inline(lines.join(" "))}</p>;
      })}
    </div>
  );
}

const TOKEN = /(\*\*[^*]+\*\*|\[\d+\])/g;

function inline(text: string): ReactNode {
  return text.split(TOKEN).map((part, index) => {
    const citation = /^\[(\d+)\]$/.exec(part);

    if (citation) {
      return (
        <sup key={index}>
          <a href={`#source-${citation[1]}`}>[{citation[1]}]</a>
        </sup>
      );
    }

    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }

    return <Fragment key={index}>{part}</Fragment>;
  });
}
