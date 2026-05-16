from dotenv import load_dotenv
import os
import time
from openai import OpenAI

load_dotenv("nvidia_api.env")
api_key = os.environ.get("NVIDIA_API_KEY")

if not api_key:
    raise ValueError("NVIDIA_API_KEY not found in environment or nvidia_api.env file")

client = OpenAI(
    base_url="https://example.invalid.com/",
    api_key=api_key
)

t0 = time.time()

response = client.chat.completions.create(
    model="nvidia/nemotron-3-super-120b-a12b",
    messages=[
        {"role": "system", "content": "You are a helpful assistant. Follow the user's instructions exactly."},
        {"role": "user", "content": "Reply with exactly one word: working"}
    ],
    temperature=1,
    top_p=0.95,
    max_tokens=100
)

latency_ms = (time.time() - t0) * 1000

print(f"Status   : OK")
print(f"Latency  : {latency_ms:.0f}ms")
print(f"Model    : {response.model}")
print(f"Response : {response.choices[0].message.content}")
print(f"Usage    : {response.usage}")

