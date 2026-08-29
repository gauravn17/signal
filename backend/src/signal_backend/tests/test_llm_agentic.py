import json
from types import SimpleNamespace

from pydantic import BaseModel

from signal_backend.services.llm import GroqLLMClient, _coerce_stringified_json


class FakeResult(BaseModel):
    answer: str


def test_coerce_stringified_json_unwraps_double_encoded_values():
    """Regression test for a real Groq quirk: some list elements come back
    as JSON-encoded strings instead of embedded objects."""
    raw = {
        "items": [
            {"a": 1},
            '{"b": 2}',  # double-encoded — must become {"b": 2}
            "plain string",  # must stay untouched
            "{not valid json",  # looks JSON-ish but isn't — must stay untouched
        ]
    }
    result = _coerce_stringified_json(raw)
    assert result["items"][0] == {"a": 1}
    assert result["items"][1] == {"b": 2}
    assert result["items"][2] == "plain string"
    assert result["items"][3] == "{not valid json"


def _completion(content=None, tool_calls=None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _tool_call(call_id, name, arguments):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=json.dumps(arguments)))


def _final_answer_completion(answer_dict):
    return _completion(tool_calls=[_tool_call("final_1", "submit_final_answer", answer_dict)])


def test_agentic_run_executes_tool_then_final_answer():
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        if kwargs.get("tool_choice") == "auto":
            if len(calls) == 1:
                return _completion(tool_calls=[_tool_call("call_1", "check_github", {"username": "octocat"})])
            return _completion(content=None, tool_calls=None)
        return _final_answer_completion({"answer": "done"})

    fake_openai = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    client = GroqLLMClient(client=fake_openai)

    executed = []

    def tool_executor(name, args):
        executed.append((name, args))
        return "octocat has 8 public repos"

    result = client.agentic_run(
        system="sys",
        user="verify this candidate",
        tools=[{"type": "function", "function": {"name": "check_github"}}],
        tool_executor=tool_executor,
        response_model=FakeResult,
        max_steps=5,
    )

    assert executed == [("check_github", {"username": "octocat"})]
    assert result.answer == "done"
    assert len(calls) == 3
    # Final call must declare a tool and force it, since some providers keep
    # emitting structured output as a tool call after a tool-using conversation.
    assert calls[-1]["tool_choice"] == {"type": "function", "function": {"name": "submit_final_answer"}}


def test_agentic_run_stops_at_max_steps():
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        if kwargs.get("tool_choice") == "auto":
            return _completion(tool_calls=[_tool_call(f"call_{len(calls)}", "check_github", {"username": "octocat"})])
        return _final_answer_completion({"answer": "forced"})

    fake_openai = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    client = GroqLLMClient(client=fake_openai)

    executed = []
    result = client.agentic_run(
        system="sys",
        user="verify",
        tools=[{"type": "function", "function": {"name": "check_github"}}],
        tool_executor=lambda name, args: executed.append((name, args)) or "ok",
        response_model=FakeResult,
        max_steps=2,
    )

    assert len(executed) == 2
    assert result.answer == "forced"
