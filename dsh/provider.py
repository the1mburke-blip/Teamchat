import json
import os
import urllib.error
import urllib.request
from pathlib import Path


def _load_env_file():
    env_path = Path(".env")
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("'\""))


def call_llm_raw(prompt: str) -> str:
    _load_env_file()

    or_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    ds_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()

    if or_key:
        url = "https://openrouter.ai/api/v1/chat/completions"
        api_key = or_key
        model_name = "deepseek/deepseek-chat"
    elif ds_key:
        url = "https://api.deepseek.com/chat/completions"
        api_key = ds_key
        model_name = "deepseek-chat"
    else:
        raise RuntimeError("Missing API Key in .env file.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API Error (HTTP {e.code}): {err_body}")


def format_code_prompt(code_context: str, instruction: str) -> str:
    return f"""TASK: {instruction}

CURRENT CODE:

```

{code_context}

```

Return ONLY the complete updated file content inside a single raw markdown code block. Do not write explanations, summaries, or status commentary."""
