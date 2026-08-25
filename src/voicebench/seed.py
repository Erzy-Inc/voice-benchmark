"""Seed the deterministic synthetic dataset used by CI + smoke runs."""
from __future__ import annotations

from pathlib import Path

from .datasets import DATASETS_DIR, seed_synthetic

SENTENCES = [
    "The quick brown fox jumps over the lazy dog",
    "Welcome to ErzyCall how can I help you today",
    "Please hold while I transfer your call to the billing department",
    "Your appointment is confirmed for Tuesday March fourth at ten thirty",
    "I need to reschedule my delivery to the downtown office",
    "Can you repeat the total amount due on this invoice",
    "Thank you for calling have a great day",
    "My phone number is five five five zero one two three",
]


def seed() -> Path:
    out = DATASETS_DIR
    out.mkdir(parents=True, exist_ok=True)
    seed_synthetic(out, SENTENCES, "core-en-synth-v1")
    return out / "core-en-synth-v1"


if __name__ == "__main__":
    print(f"seeded: {seed()}")
