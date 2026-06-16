"""Generate a SYNTHETIC demonstration of the 9-call diagnostic table.

No API is called — the 9 "responses" are hand-written to mimic the call-to-call disagreement that
temperature>0 produces, so you can see the diagnostic surface (per-call totals, consensus rate,
std-dev) populated. Every raw response is prefixed "SYNTHETIC DEMO" so it is never mistaken for a
real DeepSeek output. Run: python -m diagnostics.demo_synthetic
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from core.models import Story
from core.motives import get_motive
from scoring_engine.providers.deepseek import DeepSeekProvider, story_total

from .build_diagnostic_table import write_tables

# 9 synthetic Achievement codings for one story. 7 see achievement imagery (AI=1) with differing
# subcategories; 2 do not — i.e. exactly the borderline call-to-call disagreement temp>0 creates.
_RESP = [
    {"AI": 1, "Need": 1, "Act": "Act+", "GA+": 1, "GA-": 0, "BP": 0, "BW": 0, "Help": 0, "F+": 1, "F-": 0, "TH": 0},
    {"AI": 1, "Need": 1, "Act": "Act+", "GA+": 0, "GA-": 0, "BP": 0, "BW": 0, "Help": 0, "F+": 1, "F-": 0, "TH": 0},
    {"AI": 1, "Need": 0, "Act": "Act+", "GA+": 1, "GA-": 0, "BP": 0, "BW": 0, "Help": 0, "F+": 0, "F-": 0, "TH": 0},
    {"AI": 1, "Need": 1, "Act": "Act+", "GA+": 1, "GA-": 0, "BP": 0, "BW": 0, "Help": 0, "F+": 1, "F-": 0, "TH": 0},
    {"AI": 1, "Need": 1, "Act": "Act+", "GA+": 0, "GA-": 0, "BP": 0, "BW": 0, "Help": 0, "F+": 0, "F-": 0, "TH": 0},
    {"AI": 1, "Need": 0, "Act": "Act+", "GA+": 0, "GA-": 0, "BP": 0, "BW": 0, "Help": 0, "F+": 1, "F-": 0, "TH": 0},
    {"AI": 1, "Need": 1, "Act": "Act+", "GA+": 1, "GA-": 0, "BP": 0, "BW": 0, "Help": 0, "F+": 1, "F-": 0, "TH": 0},
    {"AI": 0, "Need": 0, "Act": None, "GA+": 0, "GA-": 0, "BP": 0, "BW": 0, "Help": 0, "F+": 0, "F-": 0, "TH": 0},
    {"AI": 0, "Need": 0, "Act": None, "GA+": 0, "GA-": 0, "BP": 0, "BW": 0, "Help": 0, "F+": 0, "F-": 0, "TH": 0},
]


def build() -> Path:
    spec = get_motive("achievement")
    story = Story.make("DEMO", 1, "A man at a drawing board works late to perfect his design.", source="live")
    prov = DeepSeekProvider.__new__(DeepSeekProvider)   # skip __init__ (no key / no client needed)
    prov.n = 9
    scored = prov._aggregate(spec, story, _RESP, attempted=9)   # 7/9 gate -> not borderline -> no API
    scored.call_logs = [{
        "motive": "achievement", "story_id": story.story_id, "picture": 1, "call_index": i + 1,
        "model": "deepseek-chat (SYNTHETIC)", "temperature": 1.0, "top_p": 1.0, "seed": None,
        "timestamp": f"2026-06-15T00:00:{i:02d}Z",
        "response_hash": hashlib.sha256(json.dumps(r, sort_keys=True).encode()).hexdigest()[:16],
        "error": "", "raw_response": "SYNTHETIC DEMO — " + json.dumps(r),
        "parsed_codes": json.dumps(r), "story_total": story_total(spec, r),
    } for i, r in enumerate(_RESP)]

    out = Path(__file__).parent
    nr, na = write_tables([scored], out / "aims_raw_call_table_DEMO.csv",
                          out / "aims_per_story_aggregate_DEMO.csv")
    print(f"SYNTHETIC demo: {nr} raw rows, {na} per-story rows. Final story score={scored.total}, "
          f"per-call totals={[l['story_total'] for l in scored.call_logs]}")
    return out


if __name__ == "__main__":
    build()
