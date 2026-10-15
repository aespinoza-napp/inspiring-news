"""
TikTok and Instagram: channels with a place in the interface and nothing
behind them yet (docs/decisions/writing.md, "Publishing").

Both platforms publish *media* - a video, a photo, a carousel of images
- with a caption. Neither takes an article: text alone cannot be posted
through either API. So before either could carry one of these articles,
the article would have to become media (a short video, or a carousel of
cards with the caption linking back to the web page), and that is a
stage of its own that does not exist.

Each says what it would need, in the reason the panel shows. Neither
makes a network call or holds a credential: there is no configuration
that turns them on, on purpose, until both the media stage and the
account and app review below exist.

Read 2026-10-15:
- TikTok: developers.tiktok.com/doc/content-posting-api-get-started and
  .../content-posting-api-reference-direct-post
- Instagram: developers.facebook.com/docs/instagram-platform/content-publishing/
"""

from __future__ import annotations

from src.models.writer.draft import ArticleDraft, PublishRecord
from src.services.publishing.publisher import ChannelUnavailable


class UnavailablePublisher:
    """A channel that refuses every call with its reason."""

    name = ""

    label = ""

    reason = ""

    def available(self) -> tuple[bool, str | None]:

        return False, self.reason

    def publish(self, draft: ArticleDraft) -> PublishRecord:

        raise ChannelUnavailable(self.name, self.reason)

    def unpublish(self, draft: ArticleDraft) -> None:

        raise ChannelUnavailable(self.name, self.reason)


class TikTokPublisher(UnavailablePublisher):

    name = "tiktok"

    label = "TikTok"

    reason = (
        "TikTok's Content Posting API posts a video or photos with a caption, not an "
        "article, so the article would first have to become one. It also needs a TikTok "
        "developer app approved for the video.publish scope, the account's authorization "
        "through Login Kit, media served from a domain verified with TikTok, and TikTok's "
        "audit of the app: until then every post is private."
    )


class InstagramPublisher(UnavailablePublisher):

    name = "instagram"

    label = "Instagram"

    reason = (
        "Instagram's content publishing API posts images, videos, reels or carousels with a "
        "caption, never text alone, so the article would first have to become images (a "
        "carousel of cards linking back to the web page). It also needs a professional "
        "(business or creator) account, a Meta app granted instagram_business_content_publish "
        "with its access token, and each image at a public URL when it is posted; at most "
        "100 posts in 24 hours."
    )
