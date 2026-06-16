"""AIMS configuration & tunables.

Everything that a pilot operator might want to change lives here (or in .env for secrets).
Nothing secret is hardcoded; API keys are read from the environment.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# ---------------------------------------------------------------- paths
DATA_DIR = BASE_DIR / "data"
FIXTURES_DIR = DATA_DIR / "fixtures"
NORMS_DIR = DATA_DIR / "norms"
REPORTS_DIR = DATA_DIR / "reports"
PICTURES_DIR = BASE_DIR / "pictures"
DB_PATH = BASE_DIR / "aims.db"
DB_URL = f"sqlite:///{DB_PATH}"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- scoring engine
# "fixture" replays the existing output CSVs (zero cost, reproduces the contract exactly).
# "deepseek" calls the live DeepSeek ensemble (requires DEEPSEEK_API_KEY).
SCORING_PROVIDER = os.getenv("AIMS_SCORING_PROVIDER", "fixture")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
# Notebook model ids are forward-dated/fictional; map to a real id here.
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")          # RAG query embeddings only
EMBEDDING_MODEL = os.getenv("AIMS_EMBEDDING_MODEL", "text-embedding-3-large")

ENSEMBLE_N = int(os.getenv("AIMS_ENSEMBLE_N", "9"))       # DeepSeek samples per story (deepseek9)
GATE_THRESHOLD = 0.5                                       # gate present if mean vote >= this
# Determinism: temperature 0 makes scoring reproducible (the validated runs relied on 9 samples,
# but for a *report* we want stable reruns). Seed is best-effort — DeepSeek's OpenAI-compatible
# API may ignore it; leave blank to omit it (temperature 0 is the real lever). See diagnostics/.
DEEPSEEK_TEMPERATURE = float(os.getenv("AIMS_DEEPSEEK_TEMPERATURE", "0.0"))
DEEPSEEK_TOP_P = float(os.getenv("AIMS_DEEPSEEK_TOP_P", "1.0"))
DEEPSEEK_SEED = os.getenv("AIMS_DEEPSEEK_SEED", "7")      # "" = don't send seed
DEEPSEEK_LOG_CALLS = os.getenv("AIMS_DEEPSEEK_LOG_CALLS", "1") == "1"  # keep raw per-call logs
MAX_RETRIES = int(os.getenv("AIMS_MAX_RETRIES", "1"))     # attempts = retries + 1
BATCH_SIZE = int(os.getenv("AIMS_BATCH_SIZE", "10"))
MAX_CONCURRENCY = int(os.getenv("AIMS_MAX_CONCURRENCY", "24"))
# Cost cap: refuse a batch whose projected spend exceeds this (USD). 0 = unlimited.
COST_CAP_USD = float(os.getenv("AIMS_COST_CAP_USD", "10"))
APPROX_USD_PER_STORY = float(os.getenv("AIMS_USD_PER_STORY", "0.10"))   # deepseek9 estimate

# Pin for reproducibility (stamped into every score row).
PROMPT_VERSION = os.getenv("AIMS_PROMPT_VERSION", "V12")
ENGINE_VERSION = os.getenv("AIMS_ENGINE_VERSION", "deepseek9")
# Which rubric the live engine sends: "v12" = the founder's verbatim V12/V11/V2 notebook prompts
# (faithful); "condensed" = the generated short rubric. Falls back to condensed if v12 files absent.
PROMPT_MODE = os.getenv("AIMS_PROMPT_MODE", "v12")
# RAG: prepend retrieved exemplars to the user message when the library embeddings + OPENAI_API_KEY
# are available. Off => zero-shot.
USE_RAG = os.getenv("AIMS_USE_RAG", "1") == "1"
RAG_K = int(os.getenv("AIMS_RAG_K", "8"))

# ---------------------------------------------------------------- aggregation
# "regression_residual" = regress motive Total on protocol word count across the cohort, use
# residuals (standard implicit-motive length correction). "none" = use raw sums (the founder's
# validated approach). Both raw and corrected are always stored; this picks which drives the report.
WORD_COUNT_CORRECTION = os.getenv("AIMS_WC_CORRECTION", "regression_residual")
PICTURES_PER_SUBJECT = int(os.getenv("AIMS_PICTURES_PER_SUBJECT", "6"))

# Percentile bands (lower-bound percentile -> label). 5 bands per the AIMS sample.
BANDS = [
    (0, "significantly low"),
    (10, "low"),
    (30, "moderate"),
    (70, "high"),
    (90, "significantly high"),
]

# ---------------------------------------------------------------- motives enabled
# Engines considered trustworthy enough to show real percentiles. Others render "[to be done]".
ENABLED_MOTIVES = [m.strip() for m in
                   os.getenv("AIMS_ENABLED_MOTIVES", "achievement,affiliation,influence").split(",")]

# Which fixture seeds the sample-relative norm distribution for each motive.
NORM_FIXTURES = {
    "achievement": "output_Achievement_V12_W1_deepseek9.csv",
    "affiliation": "output_Affiliation_V2_W1.csv",
    "influence": "output_Power_V11_W1_deepseek9.csv",
}
# Percentiles are sample-relative until a real external norm table is supplied.
NORMS_ARE_SAMPLE_RELATIVE = os.getenv("AIMS_NORMS_SAMPLE_RELATIVE", "1") == "1"

# ---------------------------------------------------------------- live PSE (Feature A; tunables)
MIN_WORDS = int(os.getenv("AIMS_MIN_WORDS", "50"))        # soft "write a bit more" nudge threshold
TIMER_SECONDS = int(os.getenv("AIMS_TIMER_SECONDS", "300"))  # per-picture (0 = no timer)
PICTURE_ORDER = os.getenv("AIMS_PICTURE_ORDER", "1,2,3,4,5,6")

# ---------------------------------------------------------------- operator auth (pilot)
OPERATOR_EMAIL = os.getenv("AIMS_OPERATOR_EMAIL", "operator@example.com")
OPERATOR_PASSWORD = os.getenv("AIMS_OPERATOR_PASSWORD", "changeme")
SECRET_KEY = os.getenv("AIMS_SECRET_KEY", "dev-secret-change-me")

# ---------------------------------------------------------------- hosted / public deployment
# Set AIMS_HOSTED=1 when running on a public URL. Then: keys come only from env (the central app),
# the Settings/API page is hidden, a passphrase gate guards the link, and live spend is capped.
HOSTED = os.getenv("AIMS_HOSTED", "0") == "1"
ACCESS_PASSPHRASE = os.getenv("AIMS_ACCESS_PASSPHRASE", "")     # required to enter when HOSTED
GLOBAL_CAP_USD = float(os.getenv("AIMS_GLOBAL_CAP_USD", "25"))  # total live-scoring spend ceiling (0=off)
RATE_LIMIT_PER_HOUR = int(os.getenv("AIMS_RATE_LIMIT_PER_HOUR", "8"))  # live evals per visitor/hour (0=off)

# Branding shown on reports.
CLIENT_NAME_DEFAULT = os.getenv("AIMS_CLIENT_NAME", "")
COPYRIGHT = "©2026 AIMS"
