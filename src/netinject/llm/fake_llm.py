"""Scripted model for CPU tests. It tests the harness only and is never used for paper results."""
from netinject.llm.base import AssistantTurn, ToolCall


class FakeLLM:
    """On its k-th turn (k = assistant messages so far) returns the k-th scripted tool call, then a final text.

    Deciding from the message history (not an internal counter) keeps it correct inside forked runs."""

    def __init__(self, script: list[tuple[str, dict]], final_text: str = "Done."):
        self.script, self.final_text = script, final_text

    def chat(self, messages, tools, temperature=0.0, seed=0) -> AssistantTurn:
        k = sum(m["role"] == "assistant" for m in messages)
        if k < len(self.script):
            name, args = self.script[k]
            return AssistantTurn(tool_calls=[ToolCall(name, dict(args))])
        return AssistantTurn(content=self.final_text)
