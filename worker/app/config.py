from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {path}. "
            f"Please create it under {ROOT_DIR / 'shared' / 'config'}."
        )
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _resolve_env_path(env_name: str, default_path: Path) -> Path:
    raw = os.getenv(env_name, str(default_path)).strip()
    p = Path(raw)
    # Resolve relative paths against project root instead of current working directory.
    return (ROOT_DIR / p).resolve() if not p.is_absolute() else p


@dataclass
class Settings:
    db_path: Path
    model_dir: Path
    export_dir: Path
    config_dir: Path
    feishu_webhook: str
    llm_provider: str
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    llm_timeout_sec: int
    github_auto_push: bool
    github_branch: str
    timezone: str

    @classmethod
    def load(cls) -> "Settings":
        load_dotenv(ROOT_DIR / "worker" / ".env")
        db_path = _resolve_env_path("DB_PATH", ROOT_DIR / "worker" / "runtime" / "fund.db")
        model_dir = _resolve_env_path("MODEL_DIR", ROOT_DIR / "worker" / "runtime" / "models")
        export_dir = _resolve_env_path("EXPORT_DIR", ROOT_DIR / "data_exports")
        config_dir = _resolve_env_path("CONFIG_DIR", ROOT_DIR / "shared" / "config")
        return cls(
            db_path=db_path,
            model_dir=model_dir,
            export_dir=export_dir,
            config_dir=config_dir,
            feishu_webhook=os.getenv("FEISHU_WEBHOOK", "").strip(),
            llm_provider=os.getenv("LLM_PROVIDER", "deepseek").strip(),
            llm_api_key=os.getenv("LLM_API_KEY", "").strip(),
            llm_base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1").strip(),
            llm_model=os.getenv("LLM_MODEL", "deepseek-chat").strip(),
            llm_timeout_sec=int(os.getenv("LLM_TIMEOUT_SEC", "40")),
            github_auto_push=os.getenv("GIT_AUTO_PUSH", "false").lower() == "true",
            github_branch=os.getenv("GITHUB_BRANCH", "main"),
            timezone=os.getenv("TZ", "Asia/Shanghai"),
        )

    def load_funds(self) -> list[dict[str, Any]]:
        return _load_json(self.config_dir / "funds.json")

    def load_strategy(self) -> dict[str, Any]:
        return _load_json(self.config_dir / "strategy.json")

    def load_news_sources(self) -> dict[str, Any]:
        return _load_json(self.config_dir / "news_sources.json")
