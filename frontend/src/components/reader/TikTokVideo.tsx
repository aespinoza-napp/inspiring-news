"use client";

import { useState } from "react";
import { safeHref } from "@/lib/links";
import { StoryVideo } from "@/lib/stories";
import styles from "./TikTokVideo.module.css";

// The player oEmbed gives for a video (docs/decisions/trends.md, "The
// story"): TikTok's own, so the video is shown without being copied.
const PLAYER = "https://www.tiktok.com/player/v1/";

// The player's id is digits; anything else is not loaded at all.
const PLAYER_ID = /^\d{5,25}$/;

/**
 * The video behind a trend, behind a click. Nothing from TikTok is loaded
 * until the reader asks: the player sets TikTok's cookies and reports the
 * visit, which a reader of this site has not agreed to by opening a story.
 * Until then the page shows what the video is and where it lives, and a
 * plain link for anyone who would rather open it on TikTok.
 */
export function TikTokVideo({
  video,
  text,
}: {
  video: StoryVideo;
  text: { title: string; notice: string; load: string; open: string; frameTitle: string };
}) {
  const [loaded, setLoaded] = useState(false);

  if (!PLAYER_ID.test(video.id)) return null;

  const link = safeHref(video.url);
  const caption = [video.title, video.author && `@${video.author.replace(/^@/, "")}`].filter(Boolean).join(" · ");

  return (
    <figure className={styles.video} data-testid="tiktok-video">
      <figcaption className={styles.caption}>
        <span className="section-label">{text.title}</span>
        {caption && <span className={styles.what}>{caption}</span>}
      </figcaption>

      {loaded ? (
        <iframe
          className={styles.player}
          src={`${PLAYER}${video.id}`}
          title={text.frameTitle}
          allow="encrypted-media; fullscreen; picture-in-picture"
          allowFullScreen
          referrerPolicy="strict-origin-when-cross-origin"
          sandbox="allow-scripts allow-same-origin allow-popups allow-presentation"
        />
      ) : (
        <div className={styles.facade}>
          <p>{text.notice}</p>
          <button type="button" onClick={() => setLoaded(true)} data-testid="tiktok-load">
            {text.load}
          </button>
          {link && (
            <a href={link} target="_blank" rel="noopener noreferrer">
              {text.open}
            </a>
          )}
        </div>
      )}
    </figure>
  );
}
