from __future__ import annotations

from typing import Any

import requests


class LLMError(Exception):
    pass


def generate_report(
    api_key: str,
    base_url: str,
    model: str,
    timeout_sec: int,
    input_payload: dict[str, Any],
) -> str:
    if not api_key:
        raise LLMError("Missing LLM_API_KEY")

    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    system_prompt = (
        "You are a prudent fund trading assistant. "
        "Output concise Chinese summary with sections: 总览, 风险提示, 建议动作."
    )
    user_prompt = (
        "根据以下结构化数据生成中文总结，必须包含置信度和风险提示，不要夸大收益，不要保证盈利。\n"
        f"{input_payload}"
    )
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
    }

    try:
        resp = requests.post(url, headers=headers, json=body, timeout=timeout_sec)
        resp.raise_for_status()
        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        if not content:
            raise LLMError("LLM response content is empty")
        return content
    except requests.RequestException as exc:
        raise LLMError(f"LLM request failed: {exc}") from exc
