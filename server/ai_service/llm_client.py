"""LLM API 客户端 - 支持 OpenAI 兼容的 LLM 调用"""

from __future__ import annotations

import os
from typing import Optional

from openai import AsyncOpenAI


class LLMClient:
    """封装大模型 API 调用"""

    def __init__(self, model: str = "gpt-4o", base_url: Optional[str] = None):
        api_key = os.getenv("OPENAI_API_KEY", "")
        url = base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.client = AsyncOpenAI(api_key=api_key, base_url=url)
        self.model = model

    async def chat(self, system_prompt: str, user_message: str, temperature: float = 0.7) -> str:
        """调用 LLM 生成回复"""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=temperature,
            max_tokens=8000,
        )
        return response.choices[0].message.content or ""
