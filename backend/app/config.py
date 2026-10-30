from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("EHDS_DATA_DIR", BACKEND_DIR / "data")))
    requests_dir: Path = field(default_factory=lambda: Path(os.getenv("EHDS_REQUESTS_DIR", BACKEND_DIR / "requests")))
    var_dir: Path = field(default_factory=lambda: Path(os.getenv("EHDS_VAR_DIR", BACKEND_DIR / "var")))
    # data/README.md: the data runs until 31 December 2025, used for ages and active medications
    reference_date: str = os.getenv("EHDS_REFERENCE_DATE", "2025-12-31")
    llm_enabled: bool = bool(os.getenv("ANTHROPIC_API_KEY")) and os.getenv("EHDS_LLM", "1") != "0"
    llm_model: str = os.getenv("EHDS_LLM_MODEL", "claude-opus-5-5")
    cors_origins: list[str] = field(default_factory=lambda: os.getenv(
        "EHDS_CORS", "http://localhost:5173,http://localhost:8080,http://localhost:3000").split(","))

    @property
    def state_db(self) -> Path:
        return Path(os.getenv("EHDS_STATE_DB", self.var_dir / "state.sqlite"))

    @property
    def spe_dir(self) -> Path:
        return self.var_dir / "spe"

    @property
    def cache_dir(self) -> Path:
        return self.var_dir / "cache"


settings = Settings()
