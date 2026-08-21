import json
from typing import Protocol, TypeVar

from openai import OpenAI
from pydantic import BaseModel

from signal_backend.config import settings

T = TypeVar("T", bound=BaseModel)


class LLMClient(Protocol):
    def structured_complete(self, system: str, user: str, response_model: type[T]) -> T: ...


class GroqLLMClient:
    """OpenAI-compatible client pointed at Groq. Swap base_url/model to change provider."""

    def __init__(self):
        self._client = OpenAI(api_key=settings.llm_api_key, base_url="https://api.groq.com/openai/v1")

    def structured_complete(self, system: str, user: str, response_model: type[T]) -> T:
        completion = self._client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
        )
        content = completion.choices[0].message.content
        return response_model.model_validate(json.loads(content))


def get_llm_client() -> LLMClient:
    return GroqLLMClient()
