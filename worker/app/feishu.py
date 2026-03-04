from __future__ import annotations

import requests


def send_text(webhook: str, title: str, text: str, timeout_sec: int = 15) -> bool:
    if not webhook:
        return False
    body = {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": title,
                    "content": [[{"tag": "text", "text": text}]],
                }
            }
        },
    }
    try:
        resp = requests.post(webhook, json=body, timeout=timeout_sec)
        resp.raise_for_status()
        return True
    except Exception:
        return False

