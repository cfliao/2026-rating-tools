import os
import argparse

from openai import OpenAI

BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-5.6-luna"


def extract_output_text(data):
    if hasattr(data, "output_text") and data.output_text:
        return data.output_text
    if isinstance(data, dict) and data.get("output_text"):
        return data["output_text"]

    if hasattr(data, "model_dump"):
        data = data.model_dump()

    texts = []
    for item in data.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                texts.append(content.get("text", ""))
    return "\n".join(texts)


def extract_token_usage(data):
    usage = getattr(data, "usage", None)
    if usage is None and isinstance(data, dict):
        usage = data.get("usage")

    if usage is None and hasattr(data, "model_dump"):
        usage = data.model_dump().get("usage", {})

    if hasattr(usage, "model_dump"):
        usage = usage.model_dump()

    usage = usage or {}
    return {
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
    }


def chat(prompt, api_key, base_url=BASE_URL, model=DEFAULT_MODEL):
    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.responses.create(
        model=model,
        input=prompt,
    )
    return extract_output_text(response), extract_token_usage(response)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=BASE_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--api-key", default=None,
                         help="OpenAI API key；未提供時讀取環境變數 OPENAI_API_KEY")
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("請用 --api-key 或設定環境變數 OPENAI_API_KEY 提供 OpenAI API key。")

    while True:
        user_input = input("You: ")
        if user_input.lower() in ("exit", "quit"):
            break
        output_text, token_usage = chat(user_input, api_key, base_url=args.base_url, model=args.model)
        print("Model:", output_text)
        print(
            "Tokens:",
            f"input={token_usage['input_tokens']}",
            f"output={token_usage['output_tokens']}",
            f"total={token_usage['total_tokens']}",
        )
