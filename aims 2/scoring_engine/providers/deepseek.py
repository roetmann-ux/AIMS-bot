"""Live DeepSeek ensemble provider.

Faithful to the notebook architecture: N independent calls (default 9), majority-voted gate at
0.5, subcategories soft-gated (averaged over only the responses whose own gate fired) with
per-category thresholds, an optional single-call DeepSeek Stage-B arbiter for borderline gates.

Reproducibility (see diagnostics/aims_nondeterminism_audit.md): calls use temperature 0 and a
best-effort seed, aggregation tie-breaks are deterministic, and every one of the N raw responses
is logged verbatim (hash + timestamp + params) onto the ScoredStory so a diagnostic table can
distinguish API-layer vs aggregation-layer variance. Failed calls are recorded, never defaulted.

Runs zero-shot by default; if RAG assets + OPENAI_API_KEY are present it prepends exemplars.
Requires a DeepSeek API key. Model ids in the notebooks are forward-dated/fictional and are
remapped via config.DEEPSEEK_MODEL.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from statistics import mean

import config
from core.models import CategoryScore, ScoredStory, Story
from core.motives import MotiveSpec, get_motive

from ..prompts import build_system_prompt, build_user_prompt, system_mode
from .base import ScoringProvider

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_json(text: str) -> dict | None:
    if not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = t[t.find("{"):] if "{" in t else t
    try:
        return json.loads(t)
    except Exception:
        m = _JSON_RE.search(t)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return None
    return None


def _gate_val(resp: dict, gate: str) -> int:
    try:
        return 1 if int(resp.get(gate, 0) or 0) == 1 else 0
    except (TypeError, ValueError):
        return 0


def story_total(spec: MotiveSpec, resp: dict) -> int:
    """Story-level Total implied by a SINGLE response (used for per-call diagnostics)."""
    if not resp or not _gate_val(resp, spec.gate_code):
        return 0
    total = 1  # gate fired
    for c in spec.categories:
        if c.code in (spec.gate_code, "TI", "UI", "HopeFear"):
            continue
        v = resp.get(c.code)
        if c.is_act_enum:
            total += 1 if v not in (None, "", "null", 0, "0") else 0
        else:
            try:
                total += 1 if int(v or 0) == 1 else 0
            except (TypeError, ValueError):
                pass
    return total


class DeepSeekProvider(ScoringProvider):
    name = "deepseek"

    def __init__(self, api_key: str = "", model: str = "", base_url: str = "", n: int = 0) -> None:
        key = api_key or config.DEEPSEEK_API_KEY
        if not key:
            raise RuntimeError("No DeepSeek API key set — add it on the Settings page (or in .env), "
                               "or choose the Sample engine to run on existing data.")
        from openai import OpenAI
        self.client = OpenAI(api_key=key, base_url=base_url or config.DEEPSEEK_BASE_URL)
        self.model = model or config.DEEPSEEK_MODEL
        self.n = n or config.ENSEMBLE_N
        self.temperature = config.DEEPSEEK_TEMPERATURE
        self.top_p = config.DEEPSEEK_TOP_P
        self.seed = int(config.DEEPSEEK_SEED) if str(config.DEEPSEEK_SEED).strip() != "" else None

    # ----------------------------------------------------------------- calls
    def _one_call(self, system: str, user: str, idx: int = -1) -> dict:
        """Return a CallResult: verbatim raw, parsed JSON, hash, timestamp, params, error."""
        kwargs = dict(model=self.model,
                      messages=[{"role": "system", "content": system},
                                {"role": "user", "content": user}],
                      response_format={"type": "json_object"},
                      temperature=self.temperature, top_p=self.top_p, timeout=120)
        if self.seed is not None:
            kwargs["seed"] = self.seed
        ts = datetime.now(timezone.utc).isoformat()
        last_err = ""
        for _ in range(config.MAX_RETRIES + 1):
            try:
                r = self.client.chat.completions.create(**kwargs)
                raw = r.choices[0].message.content or ""
                return {"call_index": idx, "raw": raw, "parsed": _parse_json(raw),
                        "hash": hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16],
                        "timestamp": ts, "error": "" if _parse_json(raw) is not None else "parse_error",
                        "temperature": self.temperature, "top_p": self.top_p, "seed": self.seed}
            except Exception as exc:
                last_err = f"{type(exc).__name__}: {exc}"
                time.sleep(2)
        return {"call_index": idx, "raw": "", "parsed": None, "hash": "", "timestamp": ts,
                "error": last_err or "request_failed", "temperature": self.temperature,
                "top_p": self.top_p, "seed": self.seed}

    def _rag(self, spec: MotiveSpec, story: Story) -> str:
        try:
            from ..rag import build_exemplars
            return build_exemplars(spec, story.text, story.picture)
        except Exception:
            return ""   # zero-shot

    # ----------------------------------------------------------------- score
    def score_story(self, story: Story, motive: str) -> ScoredStory:
        spec = get_motive(motive)
        exemplars = self._rag(spec, story)                 # "" unless RAG is active
        system = build_system_prompt(spec)                 # verbatim V12 if PROMPT_MODE=v12
        user = build_user_prompt(spec, story.text, story.picture, exemplars)
        workers = min(self.n, config.MAX_CONCURRENCY)
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(self._one_call, system, user, i) for i in range(self.n)]
            calls = [f.result() for f in futures]   # submission order -> deterministic ordering
        parsed = [c["parsed"] for c in calls if isinstance(c["parsed"], dict)]
        out = self._aggregate(spec, story, parsed, attempted=self.n)
        # Honest provenance: stamp the ACTUAL rubric used + a hash of the exact prompt sent.
        # Reads "V12-rag:<hash>" only when the verbatim V12 prompt + RAG truly ran.
        mode_tag = system_mode(spec)
        rag_tag = "rag" if exemplars else "zeroshot"
        prompt_hash = hashlib.sha256(system.encode("utf-8")).hexdigest()[:12]
        out.prompt_version = f"{mode_tag}-{rag_tag}:{prompt_hash}"
        out.engine_version = f"{mode_tag}-{rag_tag}/deepseek{self.n}@T{self.temperature}"
        if config.DEEPSEEK_LOG_CALLS:
            out.call_logs = [{
                "motive": spec.key, "story_id": story.story_id, "picture": story.picture,
                "call_index": c["call_index"] + 1, "model": self.model,
                "temperature": c["temperature"], "top_p": c["top_p"], "seed": c["seed"],
                "timestamp": c["timestamp"], "response_hash": c["hash"], "error": c["error"],
                "raw_response": c["raw"],
                "parsed_codes": (json.dumps({k: v for k, v in c["parsed"].items()
                                             if k != "explanation"}) if c["parsed"] else ""),
                "story_total": story_total(spec, c["parsed"]) if c["parsed"] else None,
            } for c in calls]
        return out

    def _aggregate(self, spec: MotiveSpec, story: Story, responses: list[dict],
                   attempted: int) -> ScoredStory:
        out = ScoredStory.empty(story, spec.key)
        out.engine_version = f"{config.PROMPT_VERSION}/{config.ENGINE_VERSION}"
        out.prompt_version = config.PROMPT_VERSION
        if not responses:
            out.stage_b_trigger = "error: no valid responses"
            return out

        gate = spec.gate_code
        gate_votes = [_gate_val(r, gate) for r in responses]
        gate_mean = mean(gate_votes) if gate_votes else 0.0
        gate_present = gate_mean >= config.GATE_THRESHOLD

        # Stage B arbiter for borderline / dissent gates. Dialect per notebook: Achievement & Power
        # fire on the first condition; Affiliation V2 is conservative and requires >= 2.
        trigger, override = "none", "no"
        conds = []
        if 0.30 <= gate_mean <= 0.70:
            conds.append("borderline_confidence")
        if not gate_present and any(gate_votes[i] and self._subs_fired(spec, responses[i])
                                    for i in range(len(responses))):
            conds.append("gate0_nonzero_dissent")
        need = 2 if spec.key == "affiliation" else 1
        if config.GATE_THRESHOLD and len(conds) >= need:
            trigger = "+".join(conds)
            arb = self._arbiter(spec, story, responses, gate_mean)
            if arb is not None and arb != gate_present:
                override, gate_present = "yes", arb

        gated = [r for r in responses if _gate_val(r, gate) == 1]
        cats: dict[str, CategoryScore] = {}
        total = 0
        for c in spec.categories:
            cs = self._cat_score(spec, c, responses, gated, gate_mean, gate_present)
            cats[c.code] = cs
            if c.code not in ("TI", "UI", "HopeFear") and cs.present:
                total += 1
        out.categories = cats
        out.gate_present = bool(gate_present)
        out.total = total if gate_present else 0
        out.provider_votes = f"deepseek={sum(gate_votes)}/{len(responses)}"
        out.stage_b_trigger = trigger
        out.stage_b_override = override
        return out

    def _subs_fired(self, spec: MotiveSpec, resp: dict) -> bool:
        return any(resp.get(c) not in (0, None, "", "0") for c in spec.subcat_codes())

    def _cat_score(self, spec, cat, responses, gated, gate_mean, gate_present) -> CategoryScore:
        code = cat.code
        if code == spec.gate_code:
            present = 1 if gate_present else 0
            return self._build_cat(code, present, "1" if present else "0", gate_mean, responses,
                                   lambda r: _gate_val(r, code), present)
        if code in ("TI",):                       # permanent 0 placeholder
            return CategoryScore(code=code, present=0, value="0")
        if not gate_present or not gated:
            return CategoryScore(code=code, present=0, value=None if cat.is_act_enum else "0")
        if cat.is_act_enum:
            acts = [str(r.get(code)) for r in gated
                    if r.get(code) not in (None, "", "null", 0, "0")]
            frac = len(acts) / len(gated)
            present = 1 if frac >= cat.threshold else 0
            value = _deterministic_mode(acts) if (present and acts) else None
            return self._build_cat(code, present, value, frac, gated,
                                   lambda r: 1 if r.get(code) not in (None, "", "null", 0, "0") else 0,
                                   present)
        vals = [1 if int(r.get(code, 0) or 0) == 1 else 0 for r in gated]
        avg = mean(vals) if vals else 0.0
        present = 1 if avg >= cat.threshold else 0
        return self._build_cat(code, present, "1" if present else "0", avg, gated,
                               lambda r: 1 if int(r.get(code, 0) or 0) == 1 else 0, present)

    def _build_cat(self, code, present, value, confidence, responses, voter, final) -> CategoryScore:
        agree, dissent = [], []
        for r in responses:
            expl = (r.get("explanation") or {}).get(code, "") if isinstance(r.get("explanation"), dict) else ""
            if not expl:
                continue
            (agree if voter(r) == final else dissent).append(expl.strip())
        agree = list(dict.fromkeys(agree))
        dissent = list(dict.fromkeys(dissent))
        return CategoryScore(code=code, present=present, value=value, confidence=round(confidence, 3),
                             explanation=(agree[0] if agree else (dissent[0] if dissent else "")),
                             majority="1" if present else "0",
                             majority_explanation="\n".join(agree),
                             dissenting_explanation="\n".join(dissent))

    def _arbiter(self, spec, story, responses, gate_mean) -> bool | None:
        from core.runtime import SETTINGS

        from ..prompts_v12 import has_v12, load_stage_b
        votes = sum(_gate_val(r, spec.gate_code) for r in responses)
        if SETTINGS.prompt_mode == "v12" and has_v12(spec.key):
            system = load_stage_b(spec.key)        # verbatim V12/V11/V2 arbiter rubric
        else:
            system = build_system_prompt(spec)
        user = (f"An ensemble was split on whether {spec.gate_code} ({spec.display_name} imagery) "
                f"is present ({votes}/{len(responses)} said yes). As the deciding arbiter, read the "
                f"story and return JSON {{\"{spec.gate_code}\": 0 or 1}}.\n\nSTORY:\n{story.text}")
        res = self._one_call(system, user, idx=-1)
        arb = res["parsed"]
        if not arb:
            return None
        return _gate_val(arb, spec.gate_code) == 1


def _deterministic_mode(items: list[str]) -> str:
    """Most common item; ties broken lexicographically so the result never depends on order."""
    counts = Counter(items)
    top = max(counts.values())
    return sorted(c for c, n in counts.items() if n == top)[0]
