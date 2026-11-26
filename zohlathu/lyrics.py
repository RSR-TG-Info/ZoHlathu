import difflib
import html
import json
import re
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Tuple

BLOG_ID = "690973182178026088"
SUMMARY_FEED = f"https://www.blogger.com/feeds/{BLOG_ID}/posts/summary"
DEFAULT_FEED = f"https://www.blogger.com/feeds/{BLOG_ID}/posts/default"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

NOISE_WORDS = {
    "official", "video", "music", "audio", "lyric", "lyrics", "mv",
    "hd", "4k", "full", "song", "songs", "mizo", "hla", "thu",
    "ft", "feat", "featuring", "cover", "version", "live", "by", "x",
}

CACHE_TTL = 3600
MAX_POST_CACHE = 200

_catalog_cache: List[Dict[str, Any]] = []
_catalog_updated_at: float = 0.0
_post_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}


def clear_cache() -> None:
    """Clear both the song index cache and cached full posts."""
    global _catalog_cache, _catalog_updated_at
    _catalog_cache = []
    _catalog_updated_at = 0.0
    _post_cache.clear()


def _fetch_json(url: str, max_retries: int = 3, timeout: int = 10) -> Optional[Dict[str, Any]]:
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(max(1, max_retries)):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(0.5 * (attempt + 1))
    return None


def _normalize(text: str) -> str:
    if not text:
        return ""
    s = text.lower()
    s = re.sub(r"[ṭţ]", "t", s)
    s = re.sub(r"[âäàá]", "a", s)
    s = re.sub(r"[êëèé]", "e", s)
    s = re.sub(r"[îïìí]", "i", s)
    s = re.sub(r"[ôöòó]", "o", s)
    s = re.sub(r"[ûüùú]", "u", s)
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _phonetic(text: str) -> str:
    """Fold common Mizo spelling variations (aw/o, ph/f, kh/k, chh/ch, dropped final h)."""
    if not text:
        return ""
    s = (
        text.replace("aw", "o")
        .replace("ph", "f")
        .replace("kh", "k")
        .replace("th", "t")
        .replace("chh", "ch")
        .replace("ngh", "ng")
    )
    s = re.sub(r"([aeiou])h\b", r"\1", s)
    return re.sub(r"([a-z])\1+", r"\1", s)


def _extract_khb_query(query: str) -> Optional[str]:
    stripped = re.sub(r"[\(\[\{].*?[\)\]\}]", " ", query)
    norm = _normalize(stripped)
    tokens = [w for w in norm.split() if w not in {"lyrics", "lyric", "song", "songs", "mizo", "video", "audio"}]
    cleaned = " ".join(tokens)

    match = re.fullmatch(
        r"(?:khb|kristian\s*hla\s*bu)\s*(?:no|num|number)?\s*0*(\d+)\s*(?:na)?(?:\s*(?:hla\s*)?thu)?",
        cleaned,
    )
    if match:
        return f"KHB {int(match.group(1))}"
    return None


def _clean_query(query: str) -> Tuple[str, List[str]]:
    stripped = re.sub(r"[\(\[\{].*?[\)\]\}]", " ", query)
    norm = _normalize(stripped)
    tokens = [w for w in norm.split() if w not in NOISE_WORDS]
    if tokens:
        return " ".join(tokens), tokens

    fallback = _normalize(query)
    return fallback, fallback.split()


def _edit_distance(a: str, b: str) -> int:
    la, lb = len(a), len(b)
    if la == 0:
        return lb
    if lb == 0:
        return la
    if abs(la - lb) > 2:
        return 99

    dp = [[0] * (lb + 1) for _ in range(la + 1)]
    for i in range(la + 1):
        dp[i][0] = i
    for j in range(lb + 1):
        dp[0][j] = j

    for i in range(1, la + 1):
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            dp[i][j] = min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                dp[i][j] = min(dp[i][j], dp[i - 2][j - 2] + cost)

    return dp[la][lb]


def _is_abbreviated(short: str, full: str) -> bool:
    """Match vowel-dropped Mizo shorthand (e.g. boihte -> bawihte, hmagaih -> hmangaih)."""
    ls, lf = len(short), len(full)
    if ls < 3 or lf <= ls or short[0] != full[0]:
        return False
    if ls == 3 and (lf > 5 or short[-1] != full[-1]):
        return False
    if (ls / lf) < 0.52 or (lf - ls) > 4:
        return False

    it = iter(full)
    return all(ch in it for ch in short)


def _word_similarity(q_word: str, target_word: str) -> float:
    if q_word == target_word:
        return 1.0
    if q_word.isdigit() or target_word.isdigit():
        return 0.0
    qp, tp = _phonetic(q_word), _phonetic(target_word)
    if qp and qp == tp and len(q_word) >= 2 and len(target_word) >= 2:
        return 0.90

    if len(q_word) >= 3 and target_word.startswith(q_word):
        return 0.88
    if len(q_word) >= 3 and q_word in target_word:
        return 0.78

    if len(q_word) >= 3 and len(target_word) >= 3:
        max_dist = 2 if len(q_word) >= 6 else 1
        dist = _edit_distance(q_word, target_word)
        if dist <= max_dist:
            return 0.86 if dist == 1 else 0.76

        if len(qp) >= 3 and len(tp) >= 3 and _edit_distance(qp, tp) <= 1:
            return 0.80

        if _is_abbreviated(q_word, target_word):
            return 0.84

    return 0.0


def _build_compounds(words: List[str]) -> List[str]:
    """Join adjacent 2- and 3-word pairs so space-merged queries still match cleanly."""
    compounds: List[str] = []
    n = len(words)
    for i in range(n - 1):
        compounds.append(words[i] + words[i + 1])
    for i in range(n - 2):
        compounds.append(words[i] + words[i + 1] + words[i + 2])
    return compounds


def _split_title(title: str) -> Tuple[str, str]:
    match = re.match(r"^(.+?)\s*[-–—]\s*(.+)$", title.strip())
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return "", title.strip()


def _parse_entry_meta(entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    title = (entry.get("title", {}).get("$t") or "").strip()
    if not title:
        return None

    raw_id = entry.get("id", {}).get("$t") or ""
    post_id = raw_id.split("post-")[-1] if "post-" in raw_id else ""

    url = ""
    for link in entry.get("link", []):
        if link.get("rel") == "alternate":
            url = link.get("href", "")
            break

    artist, song = _split_title(title)
    song_norm = _normalize(song)
    artist_norm = _normalize(artist)
    song_words = song_norm.split()
    artist_words = [w for w in artist_norm.split() if w not in NOISE_WORDS] or artist_norm.split()

    song_compact = "".join(song_words)
    artist_compact = "".join(artist_words)

    summary_text = entry.get("summary", {}).get("$t") or ""
    khb_match = re.search(r"\bKHB\s*[-#:.]?\s*0*(\d+)\b", f"{title} {summary_text}", re.I)
    khb = f"KHB {int(khb_match.group(1))}" if khb_match else ""

    return {
        "id": post_id,
        "title": title,
        "artist": artist,
        "song": song,
        "url": url,
        "khb": khb,
        "song_norm": song_norm,
        "artist_norm": artist_norm,
        "full_norm": _normalize(title),
        "song_words": song_words,
        "artist_words": artist_words,
        "song_compounds": _build_compounds(song_words),
        "artist_compounds": _build_compounds(artist_words),
        "song_compact": song_compact,
        "song_phon_compact": _phonetic(song_norm).replace(" ", ""),
        "full_compact": artist_compact + song_compact,
        "rev_full_compact": song_compact + artist_compact,
    }


def _get_catalog(max_retries: int = 3) -> List[Dict[str, Any]]:
    global _catalog_cache, _catalog_updated_at
    if _catalog_cache and (time.time() - _catalog_updated_at) < CACHE_TTL:
        return _catalog_cache

    items: List[Dict[str, Any]] = []
    start_index = 1
    batch_size = 500

    while True:
        url = f"{SUMMARY_FEED}?alt=json&max-results={batch_size}&start-index={start_index}"
        data = _fetch_json(url, max_retries=max_retries)
        if not data or "feed" not in data:
            break

        feed = data["feed"]
        entries = feed.get("entry", [])
        if not entries:
            break

        for entry in entries:
            meta = _parse_entry_meta(entry)
            if meta:
                items.append(meta)

        total = int(feed.get("openSearch$totalResults", {}).get("$t") or 0)
        start_index += len(entries)
        if start_index > total:
            break

    if items:
        _catalog_cache = items
        _catalog_updated_at = time.time()
    return _catalog_cache


def _compact_similarity(q_norm: str, item: Dict[str, Any]) -> Tuple[float, float]:
    """Space-agnostic similarity to handle joined/split words and typos."""
    q_compact = q_norm.replace(" ", "")
    s_compact = item["song_compact"]
    if len(q_compact) < 4 or not s_compact:
        return 0.0, 0.0

    if q_compact == s_compact:
        return 0.98, 1.0
    if q_compact == item["full_compact"] or q_compact == item["rev_full_compact"]:
        return 0.97, 1.0
    if len(q_compact) >= 5 and q_compact in s_compact:
        ratio = len(q_compact) / len(s_compact)
        if ratio >= 0.45:
            return round(min(0.95, 0.85 + 0.10 * ratio), 4), 1.0

    q_phon_compact = _phonetic(q_norm).replace(" ", "")
    s_phon_compact = item["song_phon_compact"]
    if len(q_phon_compact) >= 5 and q_phon_compact == s_phon_compact:
        return 0.93, 1.0

    if len(q_compact) >= 6:
        max_len_diff = max(3, int(max(len(q_compact), len(s_compact)) * 0.35))
        if abs(len(q_compact) - len(s_compact)) <= max_len_diff:
            seq_ratio = difflib.SequenceMatcher(None, q_compact, s_compact).ratio()
            if seq_ratio >= 0.80:
                return round(min(0.95, seq_ratio), 4), 1.0

        if s_phon_compact and abs(len(q_phon_compact) - len(s_phon_compact)) <= max_len_diff:
            phon_ratio = difflib.SequenceMatcher(None, q_phon_compact, s_phon_compact).ratio()
            if phon_ratio >= 0.84:
                return round(min(0.92, phon_ratio * 0.96), 4), 1.0

    return 0.0, 0.0


def _fuse_split_query_tokens(q_tokens: List[str], target_words: List[str]) -> List[str]:
    """Merge adjacent query tokens when user split a single title word (e.g. 'tawn mang' -> 'tawnmang')."""
    if len(q_tokens) < 2 or not target_words:
        return q_tokens

    fused: List[str] = []
    i = 0
    while i < len(q_tokens):
        if i + 1 < len(q_tokens):
            pair = q_tokens[i] + q_tokens[i + 1]
            pair_sim = max((_word_similarity(pair, w) for w in target_words), default=0.0)
            single_a = max((_word_similarity(q_tokens[i], w) for w in target_words), default=0.0)
            single_b = max((_word_similarity(q_tokens[i + 1], w) for w in target_words), default=0.0)
            if pair_sim >= 0.85 and pair_sim > max(single_a, single_b):
                fused.append(pair)
                i += 2
                continue
        fused.append(q_tokens[i])
        i += 1
    return fused


def _score_catalog_item(q_norm: str, q_tokens: List[str], item: Dict[str, Any]) -> Tuple[float, float]:
    if not q_tokens:
        return 0.0, 0.0

    if q_norm == item["song_norm"] or q_norm == item["full_norm"]:
        return 1.0, 1.0

    if f" {q_norm} " in f" {item['song_norm']} ":
        ratio = len(q_norm) / max(len(item["song_norm"]), 1)
        return min(0.98, 0.89 + (0.09 * ratio)), 1.0

    compact_conf, compact_cov = _compact_similarity(q_norm, item)

    eff_tokens = _fuse_split_query_tokens(q_tokens, item["song_words"] + item["artist_words"])
    matched = 0
    song_hits = 0
    song_words_covered = 0
    score_sum = 0.0

    for qt in eff_tokens:
        best_song_word = max((_word_similarity(qt, w) for w in item["song_words"]), default=0.0)
        best_song_comp = max((_word_similarity(qt, c) for c in item["song_compounds"]), default=0.0) * 0.96
        best_song = max(best_song_word, best_song_comp)

        best_art_word = max((_word_similarity(qt, w) for w in item["artist_words"]), default=0.0)
        best_art_comp = max((_word_similarity(qt, c) for c in item["artist_compounds"]), default=0.0) * 0.96
        best_artist = max(best_art_word, best_art_comp)

        if best_song >= best_artist and best_song >= 0.72:
            matched += 1
            song_hits += 1
            song_words_covered += 2 if best_song_comp > best_song_word else 1
            score_sum += best_song
        elif best_artist >= 0.78:
            matched += 1
            score_sum += best_artist * 0.92

    token_conf = 0.0
    token_cov = 0.0
    if matched > 0:
        token_cov = matched / len(eff_tokens)
        avg_sim = score_sum / len(eff_tokens)
        song_cov = min(1.0, song_words_covered / max(len(item["song_words"]), 1))
        token_conf = (avg_sim * 0.82) + (song_cov * 0.18)

        if song_hits == 0:
            token_conf *= 0.65

        token_conf = round(min(token_conf, 0.99), 4)
        token_cov = round(token_cov, 4)

    if compact_conf > token_conf:
        return compact_conf, compact_cov
    return token_conf, token_cov


class _LyricsHTMLParser(HTMLParser):
    """Extract clean visible lyrics while preserving exact single-line and stanza breaks."""

    _VOID_TAGS = {
        "area", "base", "br", "col", "embed", "hr", "img",
        "input", "link", "meta", "param", "source", "track", "wbr",
    }
    _SKIP_TAGS = {"script", "style", "iframe", "noscript"}
    _BLOCK_TAGS = {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "tr"}
    _SKIP_CLASS_RE = re.compile(r"\b(?:lyrics-credit-box|rsrtag|khb)\b", re.I)
    _HIDDEN_STYLE_RE = re.compile(r"display\s*:\s*none", re.I)

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tokens: List[Tuple[str, str]] = []
        self._skip_stack: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        t = tag.lower()
        if self._skip_stack:
            if t not in self._VOID_TAGS:
                self._skip_stack.append(t)
            return

        if t in self._SKIP_TAGS:
            self._skip_stack.append(t)
            return

        attr_map = dict(attrs)
        cls = attr_map.get("class") or ""
        style = attr_map.get("style") or ""
        if t not in self._VOID_TAGS and (self._SKIP_CLASS_RE.search(cls) or self._HIDDEN_STYLE_RE.search(style)):
            self._skip_stack.append(t)
            return

        if t == "br":
            self.tokens.append(("br", ""))
        elif t in self._BLOCK_TAGS:
            self.tokens.append(("open", t))

    def handle_startendtag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if not self._skip_stack and tag.lower() == "br":
            self.tokens.append(("br", ""))

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if self._skip_stack:
            if t in self._skip_stack:
                while self._skip_stack:
                    if self._skip_stack.pop() == t:
                        break
            return

        if t in self._BLOCK_TAGS:
            self.tokens.append(("close", t))

    def handle_data(self, data: str) -> None:
        if self._skip_stack or not data:
            return
        has_nbsp = "\xa0" in data
        cleaned = re.sub(r"\s+", " ", data.replace("\xa0", " "))
        if cleaned.strip():
            self.tokens.append(("text", cleaned))
        elif has_nbsp:
            self.tokens.append(("nbsp", ""))
        elif cleaned:
            self.tokens.append(("space", ""))

    def get_lyrics(self) -> str:
        p_multiline = 0
        p_empty_spacer = 0
        saw_p = False
        p_stack: List[Dict[str, bool]] = []

        for kind, val in self.tokens:
            if kind == "open" and val == "p":
                saw_p = True
                p_stack.append({"has_text": False, "saw_br_after_text": False, "is_multiline": False})
            elif kind == "text" and p_stack:
                st = p_stack[-1]
                if st["saw_br_after_text"]:
                    st["is_multiline"] = True
                st["has_text"] = True
            elif kind == "br":
                if p_stack:
                    if p_stack[-1]["has_text"]:
                        p_stack[-1]["saw_br_after_text"] = True
                elif saw_p:
                    p_empty_spacer += 1
            elif kind == "close" and val == "p" and p_stack:
                st = p_stack.pop()
                if st["is_multiline"]:
                    p_multiline += 1
                elif not st["has_text"]:
                    p_empty_spacer += 1

        p_is_paragraph = (p_multiline > 0) or (p_empty_spacer == 0)

        lines: List[str] = []
        cur: List[str] = []
        br_run = 0
        block_stack: List[Dict[str, Any]] = []

        def flush_cur() -> bool:
            line = re.sub(r"\s+", " ", "".join(cur)).strip()
            cur.clear()
            if line:
                lines.append(line)
                return True
            return False

        def add_blank() -> None:
            if lines and lines[-1] != "":
                lines.append("")

        for kind, val in self.tokens:
            if kind == "text":
                if br_run >= 2:
                    add_blank()
                br_run = 0
                cur.append(val)
                for frame in block_stack:
                    frame["has_text"] = True
            elif kind == "space":
                if cur:
                    cur.append(" ")
            elif kind == "nbsp":
                if cur:
                    cur.append(" ")
                if block_stack:
                    block_stack[-1]["has_nbsp"] = True
            elif kind == "br":
                if flush_cur():
                    br_run = 1
                elif lines:
                    br_run += 1
                if block_stack:
                    block_stack[-1]["has_br"] = True
            elif kind == "open":
                if block_stack:
                    block_stack[-1]["has_child"] = True
                if flush_cur():
                    br_run = 1
                block_stack.append({
                    "tag": val,
                    "has_text": False,
                    "has_br": False,
                    "has_nbsp": False,
                    "has_child": False,
                })
            elif kind == "close":
                frame = None
                for idx in range(len(block_stack) - 1, -1, -1):
                    if block_stack[idx]["tag"] == val:
                        frame = block_stack.pop(idx)
                        break
                if flush_cur():
                    br_run = 1
                if frame is not None and lines:
                    if val == "p" and p_is_paragraph:
                        add_blank()
                        br_run = 1
                    elif not frame["has_text"] and not frame["has_child"] and (frame["has_br"] or frame["has_nbsp"]):
                        add_blank()
                        br_run = 1
                    elif frame["has_text"]:
                        br_run = max(br_run, 1)

        flush_cur()
        while lines and lines[-1] == "":
            lines.pop()

        return "\n".join(lines)


def _parse_post_body(raw_html: str) -> Dict[str, Any]:
    yt_url = ""
    yt_match = re.search(
        r'youtube-src-id=["\']([a-zA-Z0-9_-]{11})["\']|youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        raw_html,
    )
    if yt_match:
        yt_id = yt_match.group(1) or yt_match.group(2)
        yt_url = f"https://youtu.be/{yt_id}"

    khb = ""
    khb_div = re.search(
        r'<div[^>]*class=["\'][^"\']*\bKHB\b[^"\']*["\'][^>]*>([\s\S]*?)</div>',
        raw_html,
        re.I,
    )
    if khb_div:
        khb_text = html.unescape(re.sub(r"<[^>]+>", " ", khb_div.group(1)))
        num_match = re.search(r"\b0*(\d+)\b", khb_text)
        khb = f"KHB {int(num_match.group(1))}" if num_match else re.sub(r"\s+", " ", khb_text).strip()
    else:
        plain_raw = re.sub(r"<[^>]+>", " ", raw_html)
        fallback_khb = re.search(r"\bKHB\s*[-#:.]?\s*0*(\d+)\b", plain_raw, re.I)
        if fallback_khb:
            khb = f"KHB {int(fallback_khb.group(1))}"

    composers: List[str] = []
    also_performed: List[str] = []

    credit_block = re.search(
        r'<div[^>]*class=["\'][^"\']*lyrics-credit-box[^"\']*["\'][^>]*>([\s\S]*)$',
        raw_html,
        re.I,
    )
    if credit_block:
        sections = re.findall(
            r'<div[^>]*class=["\'][^"\']*credit-title[^"\']*["\'][^>]*>([\s\S]*?)</div>'
            r'[\s\S]*?<ul[^>]*class=["\'][^"\']*credit-list[^"\']*["\'][^>]*>([\s\S]*?)</ul>',
            credit_block.group(1),
            re.I,
        )
        for sec_title, sec_list in sections:
            label = re.sub(r"<[^>]+>", "", sec_title).lower()
            names = [
                html.unescape(re.sub(r"<[^>]+>", "", li)).strip()
                for li in re.findall(r"<li[^>]*>([\s\S]*?)</li>", sec_list, re.I)
            ]
            names = [n for n in names if n]
            if "composer" in label or "translator" in label:
                composers.extend(names)
            elif "performed" in label:
                also_performed.extend(names)

    parser = _LyricsHTMLParser()
    parser.feed(raw_html)
    parser.close()

    return {
        "lyrics": parser.get_lyrics(),
        "khb": khb,
        "composers": composers,
        "also_performed_by": also_performed,
        "youtube_url": yt_url,
    }


def _build_post_result(entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    meta = _parse_entry_meta(entry)
    raw_html = entry.get("content", {}).get("$t") or ""
    if not meta or not raw_html:
        return None

    parsed = _parse_post_body(raw_html)
    if not parsed["lyrics"]:
        return None

    return {
        "title": meta["title"],
        "artist": meta["artist"],
        "song": meta["song"],
        "khb": parsed["khb"] or meta["khb"],
        "lyrics": parsed["lyrics"],
        "source_url": meta["url"],
        "composers": parsed["composers"],
        "also_performed_by": parsed["also_performed_by"],
        "youtube_url": parsed["youtube_url"],
    }


def _cache_put(key: str, post: Dict[str, Any]) -> None:
    if len(_post_cache) >= MAX_POST_CACHE:
        oldest_key = min(_post_cache, key=lambda k: _post_cache[k][0])
        _post_cache.pop(oldest_key, None)
    _post_cache[key] = (time.time(), post)


def _get_full_post(post_id: str, max_retries: int = 3) -> Optional[Dict[str, Any]]:
    if not post_id:
        return None

    cached = _post_cache.get(post_id)
    if cached and (time.time() - cached[0]) < CACHE_TTL:
        return dict(cached[1])

    data = _fetch_json(f"{DEFAULT_FEED}/{post_id}?alt=json", max_retries=max_retries)
    if not data or "entry" not in data:
        return None

    post = _build_post_result(data["entry"])
    if not post:
        return None

    _cache_put(post_id, post)
    return dict(post)


def _search_khb(target_khb: str, max_retries: int = 3) -> Optional[Dict[str, Any]]:
    cache_key = f"khb:{target_khb.lower()}"
    cached = _post_cache.get(cache_key)
    if cached and (time.time() - cached[0]) < CACHE_TTL:
        return dict(cached[1])

    for item in _catalog_cache:
        if item["khb"].lower() == target_khb.lower():
            post = _get_full_post(item["id"], max_retries=max_retries)
            if post:
                _cache_put(cache_key, post)
                return post

    for raw_q, limit in ((f'"{target_khb}"', 10), (target_khb, 15)):
        encoded = urllib.parse.quote_plus(raw_q)
        data = _fetch_json(f"{DEFAULT_FEED}?alt=json&q={encoded}&max-results={limit}", max_retries=max_retries)
        entries = (data or {}).get("feed", {}).get("entry", [])

        for entry in entries:
            post = _build_post_result(entry)
            if post and post["khb"].lower() == target_khb.lower():
                _cache_put(cache_key, post)
                return dict(post)

    return None


def _score_full_post(q_norm: str, q_tokens: List[str], post: Dict[str, Any]) -> float:
    meta_text = " ".join([
        post["title"],
        post["khb"],
        " ".join(post["composers"]),
        " ".join(post["also_performed_by"]),
    ])
    meta_words = _normalize(meta_text).split()
    meta_targets = meta_words + _build_compounds(meta_words)

    lyrics_norm = _normalize(post["lyrics"])
    lyrics_words = set(lyrics_norm.split())
    lyrics_compact = lyrics_norm.replace(" ", "")
    q_compact = q_norm.replace(" ", "")
    if len(q_tokens) >= 3 and f" {q_norm} " in f" {lyrics_norm} ":
        return 0.92
    if len(q_compact) >= 10 and q_compact in lyrics_compact:
        return 0.90

    eff_tokens = _fuse_split_query_tokens(q_tokens, meta_words)
    meta_hits = 0
    lyric_hits = 0
    sim_sum = 0.0

    for qt in eff_tokens:
        best_meta = max((_word_similarity(qt, w) for w in meta_targets), default=0.0)
        if best_meta >= 0.75:
            meta_hits += 1
            sim_sum += best_meta
        elif (
            qt in lyrics_words
            or (len(qt) >= 4 and not qt.isdigit() and any(w.startswith(qt) for w in lyrics_words))
            or (len(qt) >= 5 and qt in lyrics_compact)
        ):
            lyric_hits += 1
            sim_sum += 0.74

    coverage = (meta_hits + lyric_hits) / max(len(eff_tokens), 1)
    if coverage < 0.75:
        return 0.0
    if len(eff_tokens) <= 2 and meta_hits == 0:
        return 0.0

    return round(sim_sum / len(eff_tokens), 4)


def _search_blogger_feed(q_norm: str, q_tokens: List[str], max_retries: int = 3) -> Optional[Dict[str, Any]]:
    encoded = urllib.parse.quote_plus(q_norm)
    data = _fetch_json(f"{DEFAULT_FEED}?alt=json&q={encoded}&max-results=8", max_retries=max_retries)
    entries = (data or {}).get("feed", {}).get("entry", [])

    best_post = None
    best_score = 0.0

    for entry in entries:
        post = _build_post_result(entry)
        if not post:
            continue
        score = _score_full_post(q_norm, q_tokens, post)
        if score > best_score:
            best_score = score
            best_post = post

    return best_post if best_score >= 0.72 else None


def get_lyrics(query: str, max_retries: int = 3) -> Optional[Dict[str, Any]]:
    """Fetch verified Mizo song lyrics from Zo Hla thu, or None if no confident match is found."""
    if not query or not isinstance(query, str) or not query.strip():
        raise ValueError("Search query must be a non-empty string.")
        
    target_khb = _extract_khb_query(query)
    if target_khb:
        return _search_khb(target_khb, max_retries=max_retries)

    q_norm, q_tokens = _clean_query(query)
    if not q_tokens:
        return None

    catalog = _get_catalog(max_retries=max_retries)
    candidates: List[Tuple[float, float, Dict[str, Any]]] = []

    for item in catalog:
        conf, cov = _score_catalog_item(q_norm, q_tokens, item)
        if conf >= 0.45:
            candidates.append((conf, cov, item))

    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)

    if candidates:
        top_conf, top_cov, top_item = candidates[0]
        required_cov = 1.0 if len(q_tokens) == 1 else 0.75
        if top_conf >= 0.74 and top_cov >= required_cov:
            return _get_full_post(top_item["id"], max_retries=max_retries)

    best_post = None
    best_score = 0.0
    for _, _, cand in candidates[:3]:
        post = _get_full_post(cand["id"], max_retries=max_retries)
        if not post:
            continue
        score = _score_full_post(q_norm, q_tokens, post)
        if score > best_score:
            best_score = score
            best_post = post

    if best_post and best_score >= 0.72:
        return best_post

    return _search_blogger_feed(q_norm, q_tokens, max_retries=max_retries)
