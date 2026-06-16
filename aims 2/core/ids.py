"""StoryID helpers. Canonical id is ``{subject_id}_PIC{n}`` e.g. ``P010_PIC1``."""
from __future__ import annotations

import re
from typing import NamedTuple

# Allows an optional trailing suffix after the picture index (e.g. transcription variants
# like ``P104_PIC1_b``), folding it back to subject P104 / picture 1.
_PIC_RE = re.compile(r"^(?P<subject>.+?)_PIC(?P<pic>\d+)(?:[_-].*)?$", re.IGNORECASE)
_PIC_ONLY_RE = re.compile(r"PIC(\d+)", re.IGNORECASE)


class ParsedId(NamedTuple):
    subject_id: str
    picture: int


def parse_story_id(story_id: str) -> ParsedId:
    """Split ``P010_PIC1`` -> (``P010``, 1). Falls back gracefully if malformed."""
    if story_id is None:
        return ParsedId("", 0)
    m = _PIC_RE.match(story_id.strip())
    if m:
        return ParsedId(m.group("subject"), int(m.group("pic")))
    # No subject prefix; recover just the picture index if present.
    m2 = _PIC_ONLY_RE.search(story_id)
    return ParsedId(story_id.strip(), int(m2.group(1)) if m2 else 0)


def make_story_id(subject_id: str, picture: int) -> str:
    return f"{subject_id}_PIC{picture}"
