"""Lexicon-based sentiment for posts (incl. visible comment text in captures).

Deterministic, dependency-free: positive/negative lexicons (EN + common Hindi/
Hinglish tokens), emoji signals, negation flip (window 3), intensifiers.
Output: {"label": positive|negative|neutral|mixed, "score": -1..1, "pos": n, "neg": n}

Covers UI Post.sentiment. Comment threads: whatever comment text the collector
captured (visible replies are part of post text) is included automatically;
dedicated per-reply threading is a noted future gap.
"""
import re

POS = frozenset("""
good great excellent amazing awesome wonderful fantastic brilliant outstanding superb
love loved like liked best better victory win won justice support supports supported
peace proud happy glad congratulations brave historic truth true right correct
welcome thank thanks praise applaud relief safe success successful progress hope
strong powerful effective efficient transparent honest fair freedom free help helpful
amazing incredible remarkable extraordinary outstanding phenomenal legendary iconic
achha badhiya shandar zabardast badhai mubarak jeet nyay sach sahi accha khushi
""".split())

NEG = frozenset("""
bad terrible awful horrible worst hate hated shame shameful disgusting pathetic
false fake lie lies lying fraud scam corrupt corruption murder killed killing death
dead fail failed failure crisis against violence violent attack attacked
arrest detained detention resign shameful biased unfair unjust wrong danger
dangerous threat alarming dictator emergency crackdown suppression oppressive
fear afraid worried concern concerning problem issue controversial row backlash
criticism criticized condemn condemned outrage brutal harsh terrible worrisome
misleading misinformation disinformation deny denies refused refuse reject
bura kharab galat jhooth dhokha anyay apradh giraftar virodh haraam haihai murdabad
""".split())

NEGATE = frozenset(["not", "no", "never", "n't", "nahi", "nahin", "mat", "na"])
INTENS = frozenset(["very", "extremely", "highly", "deeply", "strongly", "bahut", "bohot"])
POS_EMOJI = ("😀😃😄😁👍❤️🔥🎉💪👏🙏✌️🤝👌💯🥳😍",)
NEG_EMOJI = ("😠😡👎💔😢😭🤬☠️⚠️🚨😞😖",)


def analyze(text: str) -> dict:
    t = (text or "").lower()
    words = re.findall(r"[a-z']+|[\u0900-\u097f]+", t)
    pos = neg = 0.0
    for i, w in enumerate(words):
        v = 0
        if w in POS:
            v = 1
        elif w in NEG:
            v = -1
        else:
            for e in POS_EMOJI[0]:
                if e and e in w:
                    v = 1
                    break
            else:
                for e in NEG_EMOJI[0]:
                    if e and e in w:
                        v = -1
                        break
        if not v:
            # standalone emoji tokens
            if w in ("👍",):
                v = 1
            continue
        window = words[max(0, i - 3):i]
        if any(n in window for n in NEGATE):
            v = -v
        if any(x in window for x in INTENS):
            v *= 1.5
        if v > 0:
            pos += v
        else:
            neg += -v
    # raw emoji scan (regex above misses emoji-only tokens)
    for ch in t:
        if ch in POS_EMOJI[0]:
            pos += 1
        elif ch in NEG_EMOJI[0]:
            neg += 1
    total = pos + neg
    if total == 0:
        return {"label": "neutral", "score": 0.0, "pos": 0, "neg": 0}
    score = round((pos - neg) / total, 3)
    if pos > 0 and neg > 0 and min(pos, neg) / max(pos, neg) > 0.4:
        label = "mixed"
    elif score >= 0.3:
        label = "positive"
    elif score <= -0.3:
        label = "negative"
    else:
        label = "neutral"
    return {"label": label, "score": score, "pos": round(pos, 1), "neg": round(neg, 1)}
