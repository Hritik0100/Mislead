"""Platform-specific DOM extractors for social SPAs (X / Facebook / Instagram).

Why this module exists: the generic collector captured `document.body.innerText`,
which on a social SPA is mostly *interface chrome* ("Find friends", "Number of
unread notifications", "To view keyboard shortcuts...", "Original audio", nav
rails). That produced records whose "post text" was UI text and whose engagement
numbers were scraped from the wrong nodes.

These extractors read the platform's own content containers:
  X          article[data-testid="tweet"] -> tweetText / User-Name / time / metrics
  Facebook   [data-ad-comet-preview] message + author + abbr[data-utime]
  Instagram  post permalink + caption node + "N likes" / "N comments" phrasing

Hard rules:
  * Never invent a value. A metric that is not present in the DOM stays ``None``
    (JSON ``null``) and is NOT coerced to 0, so absence is never reported as a
    real zero.
  * Never read cookies, tokens or storage. Only rendered content.
  * No bypass of any challenge: a challenge page simply yields no posts, and the
    caller runs the existing fail-closed challenge classifier on the page text.
"""
import json
import re
from typing import Any

# ---------- shared JS helpers (inlined into each extractor) ----------

_NUM_JS = r"""
const _num = (s) => {
  if (s === null || s === undefined) return null;
  const t = String(s).replace(/[,\u00a0\s]/g, '');
  const m = t.match(/([0-9]*\.?[0-9]+)\s*([KMB])?/i);
  if (!m) return null;
  let v = parseFloat(m[1]);
  const suf = (m[2] || '').toUpperCase();
  if (suf === 'K') v *= 1e3; else if (suf === 'M') v *= 1e6; else if (suf === 'B') v *= 1e9;
  return Math.round(v);
};
const _abs = (h) => { try { return new URL(h, location.origin).href; } catch (e) { return ''; } };
const _txt = (el) => el && el.innerText ? el.innerText.trim() : '';
"""


# ---------- X (Twitter) ----------

X_POSTS_JS = (
    "(() => {\n"
    + _NUM_JS +
    r"""
const out = [];
const arts = Array.from(document.querySelectorAll(
  'article[data-testid="tweet"], article[role="article"]'));
for (const a of arts) {
  const un = a.querySelector('[data-testid="User-Name"]');
  const unTxt = _txt(un);
  const hm = unTxt.match(/@([A-Za-z0-9_]{1,15})/);
  const handle = hm ? hm[1] : '';
  const lines = unTxt.split('\n').map(s => s.trim()).filter(Boolean);
  let display = '';
  for (const l of lines) { if (!/^@/.test(l) && !/^\d+[hdmwy]$/.test(l) && l !== '·') { display = l; break; } }
  const tt = a.querySelector('[data-testid="tweetText"]');
  const pa = a.querySelector('a[href*="/status/"]');
  const timeEl = a.querySelector('time[datetime]');
  const social = a.querySelector('[data-testid="socialContext"]');
  // Engagement counts live in the action group's aria-label, e.g.
  // "3 replies, 2 reposts, 22 likes, 1171 views". The *Count testids are only
  // present in some layouts, so keep them as a fallback.
  const grp = a.querySelector('div[role="group"][aria-label]');
  const gl = grp ? (grp.getAttribute('aria-label') || '') : '';
  const fromAria = (words) => {
    const m = gl.match(new RegExp('([\\d.,]+[KMB]?)\\s+(?:' + words + ')', 'i'));
    return m ? _num(m[1]) : null;
  };
  const cnt = (id) => {
    const el = a.querySelector('[data-testid="' + id + '"]');
    return el ? _num(_txt(el)) : null;
  };
  out.push({
    platform: 'x',
    handle: handle,
    display_name: display,
    verified: !!a.querySelector('svg[data-testid="icon-verified"]'),
    text: _txt(tt),
    lang: tt ? (tt.getAttribute('lang') || '') : '',
    permalink: pa ? _abs(pa.getAttribute('href')) : '',
    published_at: timeEl ? (timeEl.getAttribute('datetime') || '') : '',
    is_repost: social ? /repost/i.test(social.innerText) : false,
    repost_of_by: (social && /reposted/i.test(social.innerText) ? _txt(social) : ''),
    metrics: {
      replies: fromAria('repl(?:y|ies)') ?? cnt('replyCount'),
      reposts: fromAria('repost(?:s)?') ?? cnt('retweetCount'),
      likes: fromAria('like(?:s)?') ?? cnt('likeCount'),
      bookmarks: fromAria('bookmark(?:s)?') ?? cnt('bookmarkCount'),
      quotes: fromAria('quote(?:s)?') ?? cnt('quoteCount'),
      views: fromAria('views?') ?? cnt('viewCount')
    },
    is_video: !!a.querySelector('[data-testid="videoComponent"], video'),
    media: Array.from(a.querySelectorAll('[data-testid="tweetPhoto"] img'))
              .map(i => i.currentSrc || i.src).filter(Boolean)
  });
}
return out;
})()
"""
)

# Overlay that must be dismissed before reading the timeline. It is an X UI
# affordance (the "?" keyboard-shortcut dialog), not page content. Recorded in
# provenance so the capture stays auditable.
X_DISMISS_JS = r"""
(() => {
  const dismissed = [];
  const dlg = Array.from(document.querySelectorAll('[role="dialog"], [aria-modal="true"]'))
    .filter(d => /keyboard shortcuts/i.test(d.innerText || ''));
  for (const d of dlg) {
    for (const b of Array.from(d.querySelectorAll('button, [role="button"]'))) {
      if (/dismiss|close|done|got it|^ok$/i.test((b.innerText || '').trim() + ' ' + (b.getAttribute('aria-label') || ''))) {
        try { b.click(); dismissed.push('dialog_button'); } catch (e) {}
        break;
      }
    }
    if (!dismissed.length) { try { d.remove(); dismissed.push('dialog_removed'); } catch (e) {} }
  }
  document.body.focus();
  return dismissed;
})()
"""


# ---------- Facebook ----------

FB_POSTS_JS = (
    "(() => {\n"
    + _NUM_JS +
    r"""
const out = [];

// Facebook ships obfuscated, per-deployment class names (x1lliihq, x78zum5, ...)
// and exposes no og: tags, no data-ad-comet-preview and no data-utime on photo /
// post permalinks. So nothing here may rely on a class or a testid. The only
// durable hooks are aria-labels and href patterns:
//
//   [aria-label^="Like: N people"]      -> the post's own reaction count
//   [aria-label^="Comment by ..."]     -> marks a COMMENT subtree (exclude it)
//   abbr                                -> the post's relative timestamp
//   href with photo/?fbid= | /posts/    -> the permalink itself

const RE_PERMA = /\/(photo\/\?fbid=\d+|posts\/\d+|permalink\.php\?story_fbid=\d+|videos\/\d+|reel\/\d+)/;
const cleanUrl = (u) => {
  try {
    const url = new URL(u, location.origin);
    // drop tracking / comment anchors so one post keeps one stable URL
    ['set', '__cft__', 'ref', 'comment_id', 'cft', '__tn__', 'comment_tracking',
     'hc_[%5B' , 'nid', 'sfnsn'].forEach(k => url.searchParams.delete(k));
    url.hash = '';
    return url.href;
  } catch (e) { return u; }
};

// The post's own reaction count is labelled; comment reactions are not.
const likeEl = document.querySelector('[aria-label^="Like:"]');
let reactions = null;
if (likeEl) {
  const m = (likeEl.getAttribute('aria-label') || '').match(/([\d.,]+[KMB]?)/i);
  if (m) reactions = _num(m[1]);
}

// Everything up to the comments block belongs to the post.
const boundary = Array.from(document.querySelectorAll('span, h2, div'))
  .find(e => {
    const t = (e.innerText || '').trim();
    return (t === 'Most relevant' || t === 'Comments') && e.children.length === 0;
  });
const isComment = (el) => !!(el.closest && el.closest('[aria-label^="Comment by "]'));

// The post card is the smallest element that contains BOTH the post's own
// reaction control and the comments block. That reliably includes the author
// header, which sits above the reaction row. Climbing by text size instead
// would run all the way up to the page wrapper and drag in the site chrome.
const commonAncestor = (a, b) => {
  let x = a;
  while (x && !x.contains(b)) x = x.parentElement;
  return x;
};
let postRoot = null;
if (likeEl && boundary) postRoot = commonAncestor(likeEl, boundary);
if (!postRoot && boundary) postRoot = boundary.parentElement || boundary;
if (!postRoot) postRoot = document.body;

// Drop any leading site-chrome leaves if the container still includes them.
const NAV_WORDS = /^(Find friends|Number of unread notifications|Facebook menu|Search Facebook|Notifications|Messenger|Home|Reels|Friends|Groups|Saved|Marketplace|Feeds|Events|Settings|Meta AI)$/;

const leaves = [];
if (postRoot) {
  const w = document.createTreeWalker(postRoot, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = w.nextNode())) {
    const t = (n.nodeValue || '').replace(/\s+/g, ' ').trim();
    if (!t) continue;
    const el = n.parentElement;
    if (!el || isComment(el)) continue;
    if (boundary && (el === boundary || boundary.contains(el))) break;
    leaves.push({ text: t, el: el });
  }
  // strip leading navigation leaves
  while (leaves.length && NAV_WORDS.test(leaves[0].text)) leaves.shift();
}

const SKIP = /^(·|•|\|)$/;
const PRIVACY = /^(Shared with Public|Public|Friends|Only me)$/i;
// Meta chrome that sits inside the post card between the author and the text.
const NOISE = /^(\d+\s+(seconds?|minutes?|hours?|days?|weeks?|months?|years?)\s+ago|view post|all reactions:?|see reactions:?|\d+\s*[smhdwy]|photo|video|reel|shared with public)$/i;
const authorLeaf = leaves.find(l => !SKIP.test(l.text) && !PRIVACY.test(l.text));
const author = authorLeaf ? authorLeaf.text : '';

const textParts = [];
if (authorLeaf) {
  for (let i = leaves.indexOf(authorLeaf) + 1; i < leaves.length; i++) {
    const t = leaves[i].text;
    if (SKIP.test(t)) continue;
    if (NOISE.test(t)) continue;
    if (/^Verified (account|page)$/i.test(t)) continue;
    if (PRIVACY.test(t)) continue;
    if (/^(Like|Comment|Share|Reply|See translation|View \d+ repl)/i.test(t)) break;
    if (/^(Most relevant|Comments)$/i.test(t)) break;
    if (/^[\d.,]+[KMB]?$/i.test(t)) continue;
    textParts.push(t);
  }
}
const text = textParts.join('\n').trim();

// Remaining numeric leaves at the tail are the post's action counts. Facebook
// only labels reactions, so comments/shares are read positionally and flagged as
// such in provenance rather than presented as certain.
const tailNums = [];
for (let i = leaves.length - 1; i >= 0 && tailNums.length < 3; i--) {
  const t = leaves[i].text;
  if (SKIP.test(t)) continue;
  if (/^[\d.,]+[KMB]?$/i.test(t)) { tailNums.unshift(_num(t)); continue; }
  break;
}
let comments = null, shares = null;
if (tailNums.length === 3) { comments = tailNums[1]; shares = tailNums[2]; }
else if (tailNums.length === 2) { comments = tailNums[1]; }

// Post timestamp: FB only renders relative time here ("6h"), so it is kept as a
// labelled relative value instead of being turned into a false precise instant.
let published = '';
const abbr = postRoot && postRoot.querySelector('abbr');
if (abbr) {
  const t = (abbr.innerText || '').trim();
  if (/^\d+\s*[smhdwy]$/i.test(t)) published = t;
}

let permalink = '';
const canon = document.querySelector('link[rel="canonical"]');
if (canon && RE_PERMA.test(canon.href)) permalink = canon.href;
if (!permalink) {
  const a = Array.from(document.querySelectorAll('a[href]'))
                  .find(x => RE_PERMA.test(x.getAttribute('href') || ''));
  if (a) permalink = a.href;
}
if (!permalink && RE_PERMA.test(location.href)) permalink = location.href;
permalink = cleanUrl(permalink);

// Post photos only. Avatars and reaction icons are also fbcdn images, and the
// photo URL carries no size markers, so naturalWidth is the only reliable
// signal. OCR needs the big one: a 32px avatar reads as pure noise.
const photos = Array.from(document.querySelectorAll('img'))
  .filter(i => (i.naturalWidth || 0) >= 400 && (i.naturalHeight || 0) >= 400)
  .sort((a, b) => (b.naturalWidth * b.naturalHeight) - (a.naturalWidth * a.naturalHeight))
  .map(i => i.currentSrc || i.src)
  .filter(s => s && /^https?:/.test(s))
  .filter((v, i, arr) => arr.indexOf(v) === i)
  .slice(0, 4);

out.push({
  platform: 'facebook',
  handle: author.replace(/^@/, ''),
  display_name: author,
  profile_url: '',
  text: text,
  // Facebook shows no written caption on most photo posts; what we store is the
  // post's own visible text, which is not always a caption.
  caption_source: 'post_text_before_comments',
  permalink: permalink,
  published_at: published,
  published_relative: published,
  is_photo: /\/photo\//.test(permalink) || !!document.querySelector('img[src*="fbcdn"]'),
  is_video: !!document.querySelector('video'),
  metrics: {
    likes: reactions,
    comments: comments,
    shares: shares,
    views: null
  },
  media: photos
});
return out;
})()
"""
)


# ---------- Instagram ----------

IG_POSTS_JS = (
    "(() => {\n"
    + _NUM_JS +
    r"""
const out = [];
// Scope to the post itself. The page body also holds every loaded comment, so
// reading document.body here would mix commenter text into the caption.
const art = document.querySelector('main article') || document.querySelector('article')
          || document.querySelector('main') || document.body;
if (!art) return out;
// Comment anchors look like /p/<id>/c/<commentid>/ and must never be stored as
// the post's URL, so prefer the canonical link and strip any comment segment.
const stripComment = (u) => u.replace(/\/c\/\d+\/?$/, '/');
let permalink = '';
const canon = document.querySelector('link[rel="canonical"]');
if (canon && /\/p\//.test(canon.href)) permalink = canon.href;
if (!permalink) {
  const all = Array.from(document.querySelectorAll('a[href*="/p/"]'));
  const real = all.find(a => (a.getAttribute('href') || '').indexOf('/c/') === -1);
  const any = real || all[0];
  if (any) permalink = _abs(any.getAttribute('href'));
}
permalink = stripComment(permalink);
if (!permalink) return out;

// Author: the profile-picture alt is the most stable handle source.
let handle = '';
const profImg = Array.from(art.querySelectorAll('img[alt]'))
  .find(i => (i.getAttribute('alt') || '').endsWith("'s profile picture"));
if (profImg) {
  handle = (profImg.getAttribute('alt') || '').replace(/'s profile picture$/, '').trim();
}
if (!handle) {
  const spans = Array.from(art.querySelectorAll('span[dir="auto"]'))
                      .map(e => (e.innerText || '').trim()).filter(Boolean);
  if (spans.length) {
    const shortest = spans.slice().sort((a, b) => a.length - b.length)[0];
    if (shortest && shortest.length <= 30 && /^[\w.]+$/.test(shortest)) handle = shortest;
  }
}

// Caption: the longest dir=auto span in the post. Older layouts put it in <h1>.
let caption = '';
const h1 = art.querySelector('h1');
if (h1) {
  const sp = h1.querySelector('span[dir="auto"]');
  caption = _txt(sp || h1);
}
let captionSource = 'h1_node';
if (!caption) {
  // The caption is the first dir=auto node that spans several lines: IG renders
  // "<handle>\n<relative time>\n<text>". Single-line nodes are UI chrome
  // ("Notifications", "Ray-Ban Meta glasses") or a bare commenter username, so
  // this separates the caption from both the page furniture and the comments.
  const spans = Array.from(art.querySelectorAll('span[dir="auto"]'))
                      .map(e => (e.innerText || '').trim())
                      .filter(t => t.length > 12 && t !== handle);
  const multiline = spans.find(t => t.indexOf('\n') !== -1);
  const byHandle = handle
    ? spans.find(t => t.toLowerCase().indexOf(handle.toLowerCase()) === 0)
    : null;
  // Record how the caption was found. Instagram's markup differs between posts,
  // and on comment-heavy posts the primary node can be missing, so the value
  // tells the analyst whether to trust the text before quoting it.
  captionSource = 'multiline_node';
  if (!multiline && byHandle) captionSource = 'handle_prefix_node';
  else if (!multiline && !byHandle) captionSource = 'longest_node_fallback';
  caption = multiline || byHandle ||
            (spans.length ? spans.slice().sort((a, b) => b.length - a.length)[0] : '');
  if (handle && multiline &&
      multiline.toLowerCase().indexOf(handle.toLowerCase()) === 0) {
    captionSource = 'multiline_node_with_handle';
  }
  // IG repeats the author handle and a relative time at the head of the caption
  // node. Strip them so the stored caption is the author's words only.
  if (caption) {
    caption = caption.split('\n').filter(function (line) {
      const t = line.trim();
      if (!t) return true;
      if (handle && t === handle) return false;
      if (/^\d+\s*[smhdw]$/i.test(t)) return false;
      return true;
    }).join('\n').trim();
  }
}
const timeEl = art.querySelector('time[datetime]');
const artTxt = (art.innerText || '');
const likesM = artTxt.match(/([\d.,]+[KMB]?)\s+likes?/i);
const cmtM = artTxt.match(/([\d.,]+[KMB]?)\s+comments?/i);
out.push({
  platform: 'instagram',
  handle: handle,
  display_name: '',
  profile_url: handle ? ('https://www.instagram.com/' + handle + '/') : '',
  text: caption,
  caption_source: captionSource,
  permalink: permalink,
  published_at: timeEl ? (timeEl.getAttribute('datetime') || '') : '',
  is_video: !!art.querySelector('video'),
  metrics: {
    likes: _num(likesM ? likesM[1] : null),
    comments: _num(cmtM ? cmtM[1] : null),
    shares: null,
    views: null
  },
  media: Array.from(art.querySelectorAll('img'))
              .map(i => i.currentSrc || i.src)
              .filter(s => s && /cdninstagram|fbcdn/.test(s)).slice(0, 4)
});
return out;
})()
"""
)


EXTRACTORS = {
    "x": X_POSTS_JS,
    "facebook": FB_POSTS_JS,
    "instagram": IG_POSTS_JS,
}

# Selector that indicates real post content has rendered. Used to wait for the
# SPA instead of a fixed sleep (Instagram's login page renders blank otherwise).
CONTENT_READY = {
    "x": 'article[data-testid="tweet"], article[role="article"], [data-testid="primaryColumn"]',
    "facebook": '[role="article"], [data-ad-comet-preview], #facebook',
    "instagram": 'main, [role="main"], form',
}


def parse_extraction(raw: str) -> list:
    """Parse eval output into a list of post dicts. Tolerant of empty output."""
    raw = (raw or "").strip()
    if not raw:
        return []
    if raw.startswith('"') and raw.endswith('"'):
        try:
            raw = json.loads(raw)
        except Exception:
            return []
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return []
    return data if isinstance(data, list) else []


def normalize_post(p: dict) -> dict:
    """Keep only known keys; drop empty records; never coerce missing -> 0."""
    handle = (p.get("handle") or "").strip().lstrip("@")
    permalink = (p.get("permalink") or "").strip()
    text = (p.get("text") or "").strip()
    media = [m for m in (p.get("media") or []) if isinstance(m, str) and m.startswith("http")]
    if not permalink and not text and not media:
        return {}
    metrics = p.get("metrics") or {}
    clean_metrics = {}
    for k in ("likes", "comments", "replies", "reposts", "shares", "views",
              "bookmarks", "quotes"):
        v = metrics.get(k, None)
        # Only a real parsed number counts. Anything else stays absent, which the
        # UI renders as "unknown/0" -- never as a genuine zero measurement.
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            continue
        clean_metrics[k] = int(v)
    # Map platform-specific counters onto the shared engagement shape the UI reads.
    eng = dict(clean_metrics)
    if "replies" in eng and "comments" not in eng:
        eng["comments"] = eng["replies"]
    if "reposts" in eng and "shares" not in eng:
        eng["shares"] = eng["reposts"]
    return {
        "platform": p.get("platform") or "",
        "handle": handle,
        "display_name": (p.get("display_name") or "").strip(),
        "profile_url": (p.get("profile_url") or "").strip(),
        "permalink": permalink,
        "text": text,
        "published_at": (p.get("published_at") or "").strip(),
        "verified": bool(p.get("verified")),
        "caption_source": (p.get("caption_source") or "").strip(),
        "is_repost": bool(p.get("is_repost")),
        "is_video": bool(p.get("is_video")),
        "repost_of_by": (p.get("repost_of_by") or "").strip(),
        "is_video": bool(p.get("is_video")),
        "is_photo": bool(p.get("is_photo")),
        "engagement": eng,
        "media": media,
    }
