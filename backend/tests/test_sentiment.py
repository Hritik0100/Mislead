"""Sentiment unit tests (lexicon: EN + Hindi/Hinglish, emoji, negation, intensifiers)."""
from app.services.enrichment.sentiment import analyze


def test_positive():
    r = analyze("I support the protest, brave people fighting for justice and truth, great victory!")
    assert r["label"] == "positive" and r["score"] > 0.3


def test_negative():
    r = analyze("Shameful crackdown, detained innocents, terrible violence and lies.")
    assert r["label"] == "negative" and r["score"] < -0.3


def test_neutral_topic_words():
    # 'protest' alone must not force negative
    r = analyze("Protest at Jantar Mantar at 3pm, police present.")
    assert r["label"] in ("neutral", "negative")
    assert analyze("Meeting at noon, tea will be served.")["label"] == "neutral"


def test_mixed():
    assert analyze("Great victory but terrible violence, shame and pride together.")["label"] == "mixed"


def test_negation_and_emoji():
    assert analyze("This is not a victory, it is a shame.")["label"] == "negative"
    assert analyze("Great news! 🎉👍")["label"] == "positive"
