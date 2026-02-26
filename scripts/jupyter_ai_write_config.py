#!/usr/bin/env python3
import json
import os
from pathlib import Path


def main() -> int:
    base_url = os.getenv("JAI_BASE_URL", os.getenv("OPENAI_BASE_URL", "http://ai-assistant:8000/v1")).strip().rstrip("/")
    api_key = os.getenv("JAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))
    default_model = os.getenv("JAI_DEFAULT_MODEL", "deepseek-chat")
    provider_id = f"openai-chat-custom:{default_model}" if default_model else None
    fields = {provider_id: {"openai_api_base": base_url}} if provider_id else {}

    config = {
        "model_provider_id": provider_id,
        "embeddings_provider_id": None,
        "completions_model_provider_id": provider_id,
        "send_with_shift_enter": False,
        "fields": fields,
        "completions_fields": fields,
        "embeddings_fields": {},
        "api_keys": {"OPENAI_API_KEY": api_key} if api_key else {},
    }

    config_path = Path.home() / ".local" / "share" / "jupyter" / "jupyter_ai" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as fp:
        json.dump(config, fp, ensure_ascii=False, indent=2)
        fp.write("\n")

    print(f"Wrote Jupyter AI config: {config_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
