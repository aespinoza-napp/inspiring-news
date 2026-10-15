"""
TikTok and Instagram: listed, never available, and they say why
(src/services/publishing/social.py).
"""

import pytest

from src.services.publishing.publisher import ChannelUnavailable
from src.services.publishing.registry import Publishers
from src.services.publishing.social import InstagramPublisher, TikTokPublisher
from src.services.publishing.web import WebPublisher
from tests.factories import create_draft


@pytest.mark.parametrize("publisher", [TikTokPublisher(), InstagramPublisher()], ids=lambda p: p.name)
def test_unavailable_with_a_reason_and_publish_is_refused(publisher):

    available, reason = publisher.available()

    assert available is False
    # The reason is what a person reads in the panel: it says the article
    # must become media, which is the missing stage.
    assert "caption" in reason and "article" in reason

    with pytest.raises(ChannelUnavailable) as refused:
        publisher.publish(create_draft(status="approved"))

    assert refused.value.reason == reason
    assert refused.value.channel == publisher.name


def test_neither_holds_a_credential_or_a_client():
    """No configuration turns them on: there is nothing to configure."""

    for publisher in (TikTokPublisher(), InstagramPublisher()):
        assert vars(publisher) == {}


def test_the_channels_are_listed_web_first(tmp_path):

    publishers = Publishers(WebPublisher(tmp_path), [TikTokPublisher(), InstagramPublisher()])

    channels = publishers.channels()

    assert [channel["name"] for channel in channels] == ["web", "tiktok", "instagram"]
    assert channels[0] == {"name": "web", "label": "Web", "available": True, "reason": None}
    assert [channel["available"] for channel in channels[1:]] == [False, False]
    assert all(channel["reason"] for channel in channels[1:])

    assert publishers.get("web") is publishers.web
    assert publishers.get("myspace") is None
