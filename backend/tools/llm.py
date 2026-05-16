from __future__ import annotations

import os
from typing import Any, Optional
from openai import AsyncOpenAI
from dotenv import load_dotenv

class LLMClient:
    """Real LLM client using Nvidia's OpenAI-compatible endpoint."""

    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://integrate.api.nvidia.com/v1") -> None:
        if not api_key:
            load_dotenv("nvidia_api.env")
            api_key = os.environ.get("NVIDIA_API_KEY")
        
        if not api_key:
            # Fallback to dummy if no key found, though in production we expect it
            self.client = None
        else:
            self.client = AsyncOpenAI(base_url=base_url, api_key=api_key)

    async def complete(self, prompt: str, model: str, max_tokens: int = 1024) -> str:
        if not self.client:
            return "LLM Error: NVIDIA_API_KEY not found."
        
        # Map logical model names to actual Nvidia model IDs if needed
        model_id = model
        if model == "nemotron-super":
            model_id = "nvidia/nemotron-3-super-120b-a12b"
        elif model == "nemotron-nano":
            model_id = "nvidia/nemotron-4-340b-instruct"
        
        try:
            response = await self.client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": "You are a precise academic research assistant. Follow the user's instructions exactly. DO NOT include conversational filler, preambles, or explanations. If the user asks for JSON, return ONLY JSON. If the user asks for a query, return ONLY the query text."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            return f"LLM Error: {str(e)}"
