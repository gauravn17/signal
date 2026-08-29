import json
from typing import Any, Callable, Protocol, TypeVar

from openai import OpenAI
from pydantic import BaseModel

from signal_backend.config import settings

T = TypeVar("T", bound=BaseModel)


def _coerce_stringified_json(obj: Any) -> Any:
    """Some models occasionally double-encode a nested object/array as a JSON
    string instead of embedding it directly — observed empirically against
    the real Groq model (not assumed), only inside list/dict values. Only
    ever replaces a string with its parsed form when that string is itself
    valid JSON, so a genuine plain-text string is never touched."""
    if isinstance(obj, dict):
        return {k: _coerce_stringified_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_coerce_stringified_json(v) for v in obj]
    if isinstance(obj, str) and obj[:1] in "{[":
        try:
            return _coerce_stringified_json(json.loads(obj))
        except (json.JSONDecodeError, ValueError):
            return obj
    return obj


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
        return response_model.model_validate(_coerce_stringified_json(json.loads(content)))

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

        # Force the final answer through an explicit tool call rather than
        # response_format json_object. Some tool-calling-native models (e.g.
        # gpt-oss on Groq), once a conversation has used real tools, keep
        # emitting structured output as a tool call regardless — and Groq
        # rejects that call if no tools are declared on the request. Forcing
        # a declared "submit_final_answer" tool sidesteps the mismatch.
        final_answer_tool = {
            "type": "function",
            "function": {
                "name": "submit_final_answer",
                "description": "Submit your final structured answer. Call this when you are done investigating.",
                "parameters": response_model.model_json_schema(),
            },
        }
        messages.append(
            {
                "role": "user",
                "content": "Call submit_final_answer now with your final answer — no further investigation.",
            }
        )
        final = self._client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            tools=[final_answer_tool],
            tool_choice={"type": "function", "function": {"name": "submit_final_answer"}},
        )
        tool_call = final.choices[0].message.tool_calls[0]
        return response_model.model_validate(json.loads(tool_call.function.arguments))


def get_llm_client() -> LLMClient:
    return GroqLLMClient()
