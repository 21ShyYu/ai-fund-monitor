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

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    system_prompt = (
        "你是谨慎的基金观察助手。"
        "你只能根据最近净值变化和当前时政热点给出研判。"
        "严禁引用或推断任何XGBoost或其他机器学习模型结果。"
        "输出中文，结构固定为：总览、风险提示、建议动作。"
    )
    user_prompt = (
        "请根据输入数据给出简洁、可执行的中文研判。"
        "不要承诺收益，不要使用绝对化表达。"
        "每条建议都要体现不确定性与风险。"
        f"\n\n输入数据:\n{input_payload}"
    )
    chat_body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
    }
    responses_body = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": f"{system_prompt}\n\n{user_prompt}"}],
            }
        ],
        "temperature": 0.2,
        "stream": False,
    }

    try:
        chat_url = f"{base_url.rstrip('/')}/chat/completions"
        resp = requests.post(chat_url, headers=headers, json=chat_body, timeout=timeout_sec)
        if resp.status_code == 404:
            responses_url = f"{base_url.rstrip('/')}/responses"
            resp = requests.post(responses_url, headers=headers, json=responses_body, timeout=timeout_sec)
        resp.raise_for_status()
        data = resp.json()

        content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        if content:
            return content

        output_text = str(data.get("output_text", "")).strip()
        if output_text:
            return output_text
        output = data.get("output", [])
        if isinstance(output, list):
            chunks: list[str] = []
            for item in output:
                for c in item.get("content", []) if isinstance(item, dict) else []:
                    txt = c.get("text", "") if isinstance(c, dict) else ""
                    if txt:
                        chunks.append(str(txt))
            merged = "\n".join(chunks).strip()
            if merged:
                return merged

        raise LLMError("LLM response content is empty")
    except requests.RequestException as exc:
        raise LLMError(f"LLM request failed: {exc}") from exc
