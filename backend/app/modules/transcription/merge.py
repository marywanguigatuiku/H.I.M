"""Pure functions (no database, no web): plan the pieces, stitch results, group paragraphs, export formats."""
import math

SEGMENT_FIELDS = ("start", "end", "text", "low")


def plan_chunks(duration: float, length: int, pad: float) -> list[dict]:
    """Splits a recording into pieces. Each piece is sent with `pad` extra seconds on both sides,
    but it only 'owns' [own_start, own_end): that is how duplicates are avoided at the joins."""
    count = max(1, math.ceil(duration / length))
    plans = []
    for i in range(count):
        own_start = i * length
        own_end = min(duration, (i + 1) * length)
        plans.append({
            "idx": i,
            "own_start": float(own_start),
            "own_end": float(own_end),
            "a": float(max(0, own_start - pad)),
            "b": float(min(duration, own_end + pad)),
            "last": i == count - 1,
        })
    return plans


def is_hallucination(raw: dict) -> bool:
    """Whisper sometimes invents text over silence. Drop segments it was itself unsure were speech."""
    no_speech = raw.get("no_speech_prob")
    logprob = raw.get("avg_logprob")
    return no_speech is not None and logprob is not None and no_speech > 0.85 and logprob < -0.8


def is_low_confidence(raw: dict) -> bool:
    logprob, ratio, no_speech = raw.get("avg_logprob"), raw.get("compression_ratio"), raw.get("no_speech_prob")
    return bool(
        (logprob is not None and logprob < -1.0)
        or (ratio is not None and ratio > 2.4)
        or (no_speech is not None and no_speech > 0.6)
    )


def _abs_words(chunk: dict) -> list[dict]:
    """All words of a piece in absolute time (needs the engine to have returned word times)."""
    out = []
    for raw in chunk["segments"]:
        for w in raw.get("words") or []:
            out.append({"w": (w.get("word") or "").strip(), "s": float(w["start"]) + chunk["a"], "e": float(w["end"]) + chunk["a"]})
    out.sort(key=lambda x: x["s"])
    return out


def choose_boundary(words: list[dict], nominal: float, window: float = 1.5) -> float:
    """Where to cut between two pieces: the longest pause near the planned cut, so no word is split."""
    best_gap, best_time = 0.15, nominal  # a pause shorter than this is not worth moving the cut for
    for prev, nxt in zip(words, words[1:]):
        gap = nxt["s"] - prev["e"]
        middle = (prev["e"] + nxt["s"]) / 2
        if gap > best_gap and abs(middle - nominal) <= window:
            best_gap, best_time = gap, middle
    return best_time


def merge_chunks(chunks: list[dict]) -> list[dict]:
    """chunks: [{"own_start", "own_end", "last", "a", "segments": [raw engine segments]}] in order.

    With word times, every word is given to exactly one piece, split at a pause near the planned cut:
    nothing is repeated and nothing is lost. Without word times we fall back to giving each segment
    to the piece that holds its midpoint, then remove repeated words at the joins."""
    bounds = []  # cut times between piece i and piece i+1
    for i in range(len(chunks) - 1):
        words = _abs_words(chunks[i])
        bounds.append(choose_boundary(words, chunks[i]["own_end"]) if words else chunks[i]["own_end"])
    merged = []
    for i, chunk in enumerate(chunks):
        lo = bounds[i - 1] if i > 0 else float("-inf")
        hi = bounds[i] if i < len(bounds) else float("inf")
        for raw in chunk["segments"]:
            if not (raw.get("text") or "").strip() or is_hallucination(raw):
                continue
            low = is_low_confidence(raw)
            if raw.get("words"):
                kept = [w for w in raw["words"]
                        if lo <= (float(w["start"]) + float(w["end"])) / 2 + chunk["a"] < hi and (w.get("word") or "").strip()]
                if not kept:
                    continue
                merged.append({
                    "start": round(float(kept[0]["start"]) + chunk["a"], 2),
                    "end": round(float(kept[-1]["end"]) + chunk["a"], 2),
                    "text": " ".join(w["word"].strip() for w in kept),
                    "low": low,
                })
            else:
                start, end = float(raw["start"]) + chunk["a"], float(raw["end"]) + chunk["a"]
                if not (lo <= (start + end) / 2 < hi):
                    continue
                merged.append({"start": round(start, 2), "end": round(end, 2), "text": raw["text"].strip(), "low": low})
    merged.sort(key=lambda s: (s["start"], s["end"]))
    return dedupe_overlaps(merged)


def _norm(word: str) -> str:
    return "".join(c for c in word.lower() if c.isalnum())


def dedupe_overlaps(segments: list[dict]) -> list[dict]:
    """Two neighbouring pieces hear the same few seconds around their join and may group those words
    differently. When a segment starts before the previous one ends, remove the words it repeats."""
    out: list[dict] = []
    for original in segments:
        seg = dict(original)
        if out and seg["start"] < out[-1]["end"] - 0.05:
            prev_norm = [_norm(w) for w in out[-1]["text"].split()]
            words = seg["text"].split()
            norm = [_norm(w) for w in words]
            best = 0
            for k in range(min(len(prev_norm), len(norm), 60), 0, -1):
                if prev_norm[-k:] == norm[:k] and all(norm[:k]):
                    best = k
                    break
            if best >= 2 or (best >= 1 and best == len(norm)):
                words = words[best:]
                if not words:
                    continue  # this segment only repeated what we already have
                seg["text"] = " ".join(words)
                seg["start"] = round(max(seg["start"], out[-1]["end"]), 2)
        out.append(seg)
    return out


def group_paragraphs(segments: list[dict], gap: float = 2.0, max_chars: int = 700) -> list[dict]:
    """Groups segments into readable paragraphs: a pause of `gap` seconds, or a long paragraph that
    just finished a sentence, starts a new one."""
    paragraphs: list[dict] = []
    current = None
    explicit = any(s.get("para") is not None for s in segments)  # the editor saved its own layout
    for i, seg in enumerate(segments):
        if current is not None:
            pause = seg["start"] - current["end"]
            long_enough = len(current["text"]) >= max_chars and current["text"].rstrip()[-1:] in ".?!"
            if bool(seg.get("para")) if explicit else (pause >= gap or long_enough):
                paragraphs.append(current)
                current = None
        if current is None:
            current = {"start": seg["start"], "end": seg["end"], "text": seg["text"], "low": bool(seg.get("low")), "first": i, "last": i}
        else:
            current["end"] = seg["end"]
            current["text"] += " " + seg["text"]
            current["low"] = current["low"] or bool(seg.get("low"))
            current["last"] = i
    if current is not None:
        paragraphs.append(current)
    return paragraphs


def full_text(segments: list[dict]) -> str:
    return "\n\n".join(p["text"] for p in group_paragraphs(segments))


def clock(seconds: float, comma: bool = False, hours: bool = True) -> str:
    total_ms = int(round(seconds * 1000))
    h, rem = divmod(total_ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    sep = "," if comma else "."
    if hours or h:
        return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"
    return f"{m:02d}:{s:02d}{sep}{ms:03d}"


def to_srt(segments: list[dict]) -> str:
    blocks = []
    for n, seg in enumerate(segments, 1):
        blocks.append(f"{n}\n{clock(seg['start'], True)} --> {clock(seg['end'], True)}\n{seg['text']}\n")
    return "\n".join(blocks)


def to_vtt(segments: list[dict]) -> str:
    blocks = ["WEBVTT\n"]
    for seg in segments:
        blocks.append(f"{clock(seg['start'])} --> {clock(seg['end'])}\n{seg['text']}\n")
    return "\n".join(blocks)


def stamp(seconds: float) -> str:
    total = int(seconds)
    return f"[{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}]"


def to_txt(segments: list[dict], timestamps: bool = False) -> str:
    parts = []
    for p in group_paragraphs(segments):
        parts.append((stamp(p["start"]) + " " if timestamps else "") + p["text"])
    return "\n\n".join(parts) + "\n"
