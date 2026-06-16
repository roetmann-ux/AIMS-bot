"""Norms: word-count correction + within-sample T / percentile.

NB (see docs/INTEGRATION_CONTRACT.md §6): the founder's notebooks compute neither a length
correction nor a percentile — participant scores are raw sums and validity is judged against
external human T-scores. So this module is *new* AIMS functionality implementing the standard
implicit-motive treatment, clearly labelled sample-relative:

  1. Length correction — regress each subject's motive Total on their protocol word count across
     the reference cohort; the corrected score is the residual re-centred to the raw mean
     (the classic control for protocol length). Toggle via config.WORD_COUNT_CORRECTION.
  2. Standardise the corrected score within the cohort -> T = 50 + 10·z, percentile = Φ(z)·100.

Percentiles are sample-relative until a real external norm table is supplied.
"""
from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np
from scipy.stats import norm as _norm

import config
from core.motives import MotiveSpec, get_motive
from scoring_engine.contract import load_fixture


def band_for_percentile(pct: float) -> str:
    label = config.BANDS[0][1]
    for lo, name in config.BANDS:
        if pct >= lo:
            label = name
    return label


@dataclass
class NormTable:
    motive: str
    n: int
    correction: str          # "regression_residual" | "none"
    slope: float
    intercept: float
    mean_raw: float
    mean_corr: float
    sd_corr: float
    sample_relative: bool = True
    version: str = ""              # hash of (cohort file + correction method + bands) for traceability
    fixture: str = ""
    corrected_scores: tuple = ()   # cohort corrected scores (for empirical checks)

    # -------------------------------------------------- build
    @classmethod
    def build(cls, motive: str, cohort: list[tuple[float, int]],
              correction: str | None = None) -> "NormTable":
        correction = correction or config.WORD_COUNT_CORRECTION
        raws = np.array([c[0] for c in cohort], dtype=float)
        words = np.array([c[1] for c in cohort], dtype=float)
        n = len(cohort)
        mean_raw = float(raws.mean()) if n else 0.0
        slope = intercept = 0.0
        if correction == "regression_residual" and n >= 3 and words.std() > 1e-9:
            slope, intercept = np.polyfit(words, raws, 1)
            corrected = raws - (slope * words + intercept) + mean_raw
        else:
            correction = "none" if correction != "none" else correction
            corrected = raws.copy()
        sd_corr = float(corrected.std(ddof=1)) if n >= 2 else 0.0
        return cls(motive=motive, n=n, correction=correction, slope=float(slope),
                   intercept=float(intercept), mean_raw=mean_raw,
                   mean_corr=float(corrected.mean()) if n else 0.0, sd_corr=sd_corr,
                   sample_relative=config.NORMS_ARE_SAMPLE_RELATIVE,
                   corrected_scores=tuple(round(float(x), 3) for x in corrected))

    # -------------------------------------------------- use
    def correct(self, raw: float, words: int) -> float:
        if self.correction == "regression_residual":
            return raw - (self.slope * words + self.intercept) + self.mean_raw
        return raw

    def standardize(self, raw: float, words: int) -> dict:
        corrected = self.correct(raw, words)
        if self.sd_corr > 1e-9:
            z = (corrected - self.mean_corr) / self.sd_corr
        else:
            z = 0.0
        t = 50.0 + 10.0 * z
        pct = int(round(float(_norm.cdf(z)) * 100))
        pct = max(1, min(99, pct))
        return {"raw": round(raw, 2), "corrected": round(corrected, 2),
                "z": round(z, 3), "t_score": round(t, 1), "percentile": pct,
                "band": band_for_percentile(pct)}


def _cohort_from_fixture(spec: MotiveSpec) -> list[tuple[float, int]]:
    fx = load_fixture(spec.key, config.FIXTURES_DIR / config.NORM_FIXTURES[spec.key])
    raw: dict[str, float] = defaultdict(float)
    words: dict[str, int] = defaultdict(int)
    for s in fx.values():
        raw[s.subject_id] += s.total
        words[s.subject_id] += s.word_count
    return [(raw[k], words[k]) for k in raw]


def _cohort_version(spec: MotiveSpec) -> str:
    """Stable hash of the reference cohort + standardisation method. Changes only if the cohort
    file, correction method, or band cutpoints change — so a percentile shift is always traceable."""
    path = config.FIXTURES_DIR / config.NORM_FIXTURES[spec.key]
    h = hashlib.sha256()
    h.update(path.read_bytes())
    h.update(config.WORD_COUNT_CORRECTION.encode())
    h.update(repr(config.BANDS).encode())
    h.update(str(config.PICTURES_PER_SUBJECT).encode())
    return h.hexdigest()[:12]


@lru_cache(maxsize=8)
def get_norms(motive: str) -> NormTable:
    spec = get_motive(motive)
    nt = NormTable.build(spec.key, _cohort_from_fixture(spec))
    nt.version = _cohort_version(spec)
    nt.fixture = config.NORM_FIXTURES[spec.key]
    return nt


def cohort_fingerprint() -> str:
    """One short id summarising the cohort versions of all enabled motives (for report metadata)."""
    parts = [f"{m}:{get_norms(m).version}" for m in config.ENABLED_MOTIVES]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:10]
