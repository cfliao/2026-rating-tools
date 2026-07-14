import requests
import argparse

BASE_URL = "http://192.168.4.89:13305/api/v1"
DEFAULT_MODEL = "gpt-oss-120b-mxfp-GGUF"

#keep: gpt-oss-20b-mxfp4-GGUF

def chat(prompt, base_url=BASE_URL, model=DEFAULT_MODEL):
    response = requests.post(
        f"{base_url}/chat/completions",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
        },
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=BASE_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    while True:
        user_input = input("You: ")
        if user_input.lower() in ("exit", "quit"):
            break
        print("Model:", chat(user_input, base_url=args.base_url, model=args.model))