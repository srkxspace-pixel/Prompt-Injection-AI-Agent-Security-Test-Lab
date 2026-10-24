"""What every model client returns. A client has one method:
    chat(messages, tools, temperature, seed) -> AssistantTurn
implemented by OllamaClient (Colab) and FakeLLM (local tests)."""
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    name: str
    args: dict


@dataclass
class AssistantTurn:
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    parsed_from_text: bool = False  # the tool call was written as plain text and recovered (format slip)
    prompt_tokens: int = 0
    output_tokens: int = 0
