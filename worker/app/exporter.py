from __future__ import annotations

import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


def export_frontend_json(
    export_dir: Path,
    latest_signals: list[dict[str, Any]],
    prediction_history: list[dict[str, Any]],
    news_items: list[dict[str, Any]],
) -> None:
    export_dir.mkdir(parents=True, exist_ok=True)

    dashboard = {
        "latest_signals": latest_signals,
        "prediction_history": prediction_history,
        "news": news_items[:120],
        "hot_terms": calc_hot_terms(news_items),
    }
    with (export_dir / "dashboard.json").open("w", encoding="utf-8") as f:
        json.dump(dashboard, f, ensure_ascii=False, indent=2)


def calc_hot_terms(news_items: list[dict[str, Any]], top_k: int = 50) -> list[dict[str, Any]]:
    stop_words = {"的", "了", "是", "和", "在", "与", "及", "就", "对", "the", "and", "for", "to", "of"}
    tokens: list[str] = []
    for row in news_items[:300]:
        text = f"{row.get('title', '')} {row.get('summary', '')}"
        for t in _simple_cut(text):
            if len(t) < 2 or t.lower() in stop_words:
                continue
            tokens.append(t.lower())
    counted = Counter(tokens).most_common(top_k)
    return [{"term": k, "count": v} for k, v in counted]


def git_auto_push(project_root: Path, branch: str) -> None:
    _run(["git", "add", "data_exports", "shared/config"], cwd=project_root)
    _run(["git", "commit", "-m", "chore: update dashboard exports"], cwd=project_root, check=False)
    _run(["git", "push", "origin", branch], cwd=project_root)


def _run(cmd: list[str], cwd: Path, check: bool = True) -> None:
    subprocess.run(cmd, cwd=str(cwd), check=check)


def _simple_cut(text: str) -> list[str]:
    output: list[str] = []
    token = []
    for ch in text:
        if ch.isalnum() or "\u4e00" <= ch <= "\u9fff":
            token.append(ch)
        else:
            if token:
                output.append("".join(token))
                token = []
    if token:
        output.append("".join(token))
    return output

