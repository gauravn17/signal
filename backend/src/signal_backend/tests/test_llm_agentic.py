import json
from types import SimpleNamespace

from pydantic import BaseModel

from signal_backend.services.llm import GroqLLMClient


class FakeResult(BaseModel):
    answer: str


def _completion(content=None, tool_calls=None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _tool_call(call_id, name, arguments):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=json.dumps(arguments)))


def test_agentic_run_executes_tool_then_final_answer():
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _completion(tool_calls=[_tool_call("call_1", "check_github", {"username": "octocat"})])
        if len(calls) == 2:
            return _completion(content=None, tool_calls=None)
        return _completion(content=json.dumps({"answer": "done"}))

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


def test_agentic_run_stops_at_max_steps():
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        if "tools" in kwargs:
            return _completion(tool_calls=[_tool_call(f"call_{len(calls)}", "check_github", {"username": "octocat"})])
        return _completion(content=json.dumps({"answer": "forced"}))

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
