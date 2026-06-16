"""Runtime settings editable from the UI (so the operator never touches .env).

Persisted to data/settings.json (gitignored, local only). API keys are read from here first,
then from the environment. For a single-operator pilot this is a pragmatic compromise; for
production move keys to a secret manager.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

import config

_PATH = config.DATA_DIR / "settings.json"


@dataclass
class Settings:
    scoring_provider: str = config.SCORING_PROVIDER       # "fixture" | "deepseek"
    deepseek_api_key: str = config.DEEPSEEK_API_KEY
    deepseek_model: str = config.DEEPSEEK_MODEL
    deepseek_base_url: str = config.DEEPSEEK_BASE_URL
    openai_api_key: str = config.OPENAI_API_KEY
    ensemble_n: int = config.ENSEMBLE_N
    prompt_mode: str = config.PROMPT_MODE          # "v12" (verbatim notebook prompts) | "condensed"
    use_rag: bool = config.USE_RAG
    enabled_motives: list = field(default_factory=lambda: list(config.ENABLED_MOTIVES))

    def has_live_key(self) -> bool:
        return bool((self.deepseek_api_key or "").strip())

    def has_openai_key(self) -> bool:
        return bool((self.openai_api_key or "").strip())

    def key_hint(self) -> str:
        k = (self.deepseek_api_key or "").strip()
        return f"set ✓ (…{k[-4:]})" if len(k) >= 4 else ("set ✓" if k else "not set")

    def openai_hint(self) -> str:
        k = (self.openai_api_key or "").strip()
        return f"set ✓ (…{k[-4:]})" if len(k) >= 4 else ("set ✓" if k else "not set")


def _load() -> Settings:
    s = Settings()
    if _PATH.exists():
        try:
            data = json.loads(_PATH.read_text())
            for k, v in data.items():
                if hasattr(s, k):
                    setattr(s, k, v)
        except Exception:
            pass
    return s


SETTINGS = _load()


def save() -> None:
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    _PATH.write_text(json.dumps(asdict(SETTINGS), indent=2))


def update(**kw) -> None:
    for k, v in kw.items():
        if hasattr(SETTINGS, k) and v is not None:
            setattr(SETTINGS, k, v)
    save()


def test_deepseek() -> tuple[bool, str]:
    """Make one tiny call to verify the key/model work. Returns (ok, message)."""
    if not SETTINGS.has_live_key():
        return False, "No DeepSeek API key set."
    try:
        from openai import OpenAI
        client = OpenAI(api_key=SETTINGS.deepseek_api_key, base_url=SETTINGS.deepseek_base_url)
        r = client.chat.completions.create(
            model=SETTINGS.deepseek_model,
            messages=[{"role": "user", "content": "Reply with the single word: ok"}],
            max_tokens=5, timeout=30)
        return True, f"Connected to {SETTINGS.deepseek_model}: “{r.choices[0].message.content.strip()}”"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
