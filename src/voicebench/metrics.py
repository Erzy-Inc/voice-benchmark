"""Scoring: WER with shared normalization (docs/METHODOLOGY.md)."""
from __future__ import annotations

import re
import unicodedata

import jiwer

# Applied identically to reference and hypothesis before scoring.
_CONTRACTIONS = {
    "i'm": "i am", "you're": "you are", "it's": "it is", "don't": "do not",
    "can't": "cannot", "won't": "will not", "isn't": "is not", "aren't": "are not",
    "they're": "they are", "we're": "we are", "that's": "that is",
    "i've": "i have", "i'll": "i will", "let's": "let us",
}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    for a, b in _CONTRACTIONS.items():
        text = re.sub(rf"\b{re.escape(a)}\b", b, text)
    # Strip punctuation except digits/letters/spaces; keep $ % for ITN slices.
    text = re.sub(r"[^a-z0-9$%\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def wer(reference: str, hypothesis: str) -> float | None:
    ref, hyp = normalize(reference), normalize(hypothesis)
    if not ref:
        return None
    try:
        return round(jiwer.wer(ref, hyp), 4)
    except Exception:
        return 1.0
