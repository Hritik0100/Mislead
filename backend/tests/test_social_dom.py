"""Tests for the platform-specific social DOM extractors.

The important invariant: a metric that is not present in the DOM must stay
absent. Reporting a missing like-count as 0 would be a fabricated measurement.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.collectors import social_dom as S  # noqa: E402


def test_extractors_exist_for_supported_platforms():
    for p in ("x", "facebook", "instagram"):
        assert p in S.EXTRACTORS
        assert S.EXTRACTORS[p].strip()
        assert p in S.CONTENT_READY


def test_missing_metric_stays_absent_not_zero():
    post = S.normalize_post({
        "platform": "x", "handle": "someone", "permalink": "https://x.com/s/status/1",
        "text": "hello", "metrics": {"likes": None, "views": 12},
    })
    assert post["engagement"]["views"] == 12
    assert "likes" not in post["engagement"]


def test_non_numeric_metric_is_discarded():
    post = S.normalize_post({
        "platform": "x", "handle": "someone", "permalink": "https://x.com/s/status/1",
        "text": "hello", "metrics": {"likes": "abc", "replies": "", "views": 3},
    })
    assert "likes" not in post["engagement"]
    assert "replies" not in post["engagement"]
    assert post["engagement"]["views"] == 3


def test_boolean_is_not_treated_as_a_number():
    post = S.normalize_post({
        "platform": "x", "handle": "a", "permalink": "https://x.com/a/status/1",
        "text": "t", "metrics": {"likes": True, "views": 1},
    })
    assert "likes" not in post["engagement"]


def test_replies_and_reposts_map_onto_shared_shape():
    post = S.normalize_post({
        "platform": "x", "handle": "a", "permalink": "https://x.com/a/status/1",
        "text": "t", "metrics": {"replies": 4, "reposts": 9},
    })
    # The UI renders comments/shares; the platform names them replies/reposts.
    assert post["engagement"]["comments"] == 4
    assert post["engagement"]["shares"] == 9


def test_handle_is_normalised_without_at_sign():
    post = S.normalize_post({
        "platform": "x", "handle": "@Some_User", "permalink": "https://x.com/Some_User/status/1",
        "text": "t",
    })
    assert post["handle"] == "Some_User"


def test_empty_post_is_rejected():
    assert S.normalize_post({"handle": "", "permalink": "", "text": "", "media": []}) == {}


def test_media_must_be_http_urls():
    post = S.normalize_post({
        "platform": "x", "handle": "a", "permalink": "https://x.com/a/status/1",
        "text": "t", "media": ["https://pbs.twimg.com/x.jpg", "javascript:alert(1)", ""],
    })
    assert post["media"] == ["https://pbs.twimg.com/x.jpg"]


def test_parse_extraction_tolerates_bad_output():
    assert S.parse_extraction("") == []
    assert S.parse_extraction("not json") == []
    assert S.parse_extraction('{"a": 1}') == []          # object, not a list
    assert S.parse_extraction('"[]"') == []              # CLI-quoted empty list
    assert len(S.parse_extraction('[{"a":1}]')) == 1


def test_evidence_html_is_captured_even_when_text_is_short():
    # A media-only post has no tweetText but must still be kept.
    post = S.normalize_post({
        "platform": "x", "handle": "a", "permalink": "https://x.com/a/status/1",
        "text": "", "media": ["https://pbs.twimg.com/x.jpg"],
    })
    assert post["permalink"] == "https://x.com/a/status/1"
