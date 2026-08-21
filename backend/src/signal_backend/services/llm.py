import json
from typing import Any, Callable, Protocol, TypeVar

from openai import OpenAI
from pydantic import BaseModel

from signal_backend.config import settings

T = TypeVar("T", bound=BaseModel)


class LLMClient(Protocol):
    def structured_complete(self, system: str, user: str, response_model: type[T]) -> T: ...

    def agentic_run(
        self,
        system: str,
        user: str,
        tools: list[dict],
        tool_executor: Callable[[str, dict], str],
        response_model: type[T],
        max_steps: int = 5,
    ) -> T: ...


class GroqLLMClient:
    """OpenAI-compatible client pointed at Groq. Swap base_url/model to change provider."""

    def __init__(self, client: Any = None):
        self._client = client or OpenAI(api_key=settings.llm_api_key, base_url="https://api.groq.com/openai/v1")

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

    def agentic_run(
        self,
        system: str,
        user: str,
        tools: list[dict],
        tool_executor: Callable[[str, dict], str],
        response_model: type[T],
        max_steps: int = 5,
    ) -> T:
        """
        Runs a tool-calling loop: the model picks a tool or stops; tool results
        are fed back until it stops calling tools (or max_steps is hit), then a
        final call forces structured JSON output matching response_model.
        """
        messages: list[dict] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        for _ in range(max_steps):
            completion = self._client.chat.completions.create(
                model=settings.llm_model, messages=messages, tools=tools, tool_choice="auto"
            )
            message = completion.choices[0].message
            if not message.tool_calls:
                break
            messages.append({"role": "assistant", "tool_calls": message.tool_calls, "content": message.content})
            for tool_call in message.tool_calls:
                result = tool_executor(tool_call.function.name, json.loads(tool_call.function.arguments))
                messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": result})

        messages.append(
            {
                "role": "user",
                "content": "Respond now with the final JSON matching the required schema, no further tool calls.",
            }
        )
        final = self._client.chat.completions.create(
            model=settings.llm_model, messages=messages, response_format={"type": "json_object"}
        )
        return response_model.model_validate(json.loads(final.choices[0].message.content))


def get_llm_client() -> LLMClient:
    return GroqLLMClient()
