"""Ollama client, used only inside the GPU notebooks (Colab, Kaggle). Needs the `ollama` package and a running server."""
import json
import re

from netinject.llm.base import AssistantTurn, ToolCall


_ARG = re.compile(r"""(\w+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^,\s)]+))""")


def parse_text_tool_calls(text: str, known: set[str]) -> list[ToolCall]:
    """Recover tool calls that a model wrote as text instead of using the tool-call field (pilot finding:
    Llama-3.1 writes JSON objects inside prose, Mistral writes name(arg="...") lines in code blocks).

    Accepts JSON objects {"name": ..., "arguments"|"parameters": {...}} anywhere in the text (any tool name, so an
    invented tool gets the normal "unknown tool" error back), and Python-style calls name(arg="...") for known tool
    names only (so prose is never mistaken for a call). Returned in the order they appear."""
    found = []  # (position, ToolCall)
    decoder = json.JSONDecoder()
    i = text.find("{")
    while i != -1:
        try:
            obj, end = decoder.raw_decode(text, i)
        except json.JSONDecodeError:
            i = text.find("{", i + 1)
            continue
        if isinstance(obj, dict) and isinstance(obj.get("name"), str) and ("arguments" in obj or "parameters" in obj):
            args = obj.get("arguments", obj.get("parameters", {}))
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = None
            if isinstance(args, dict):
                found.append((i, ToolCall(obj["name"], args)))
        i = text.find("{", end if isinstance(obj, dict) else i + 1)
    if known:
        for m in re.finditer(r"\b(" + "|".join(map(re.escape, known)) + r")\s*\(([^()]*)\)", text):
            args = {k: next(v for v in vals if v) if any(vals) else "" for k, *vals in _ARG.findall(m.group(2))}
            found.append((m.start(), ToolCall(m.group(1), args)))
    return [call for _, call in sorted(found, key=lambda x: x[0])]


class OllamaClient:
    def __init__(self, tag: str, num_ctx: int = 8192, num_predict: int = 512, host: str = "http://127.0.0.1:11434"):
        import ollama  # imported here so local CPU code never needs it

        self.tag, self.num_ctx, self.num_predict = tag, num_ctx, num_predict
        self.client = ollama.Client(host=host, timeout=300)

    def chat(self, messages, tools, temperature=0.0, seed=0) -> AssistantTurn:
        r = self.client.chat(model=self.tag, messages=messages, tools=tools,
                             options={"temperature": temperature, "seed": seed,
                                      "num_ctx": self.num_ctx, "num_predict": self.num_predict})
        msg = r.message
        calls = [ToolCall(tc.function.name, dict(tc.function.arguments or {})) for tc in (msg.tool_calls or [])]
        from_text = False
        if not calls and msg.content:
            calls = parse_text_tool_calls(msg.content, {t["function"]["name"] for t in tools})
            from_text = bool(calls)
        return AssistantTurn(content=msg.content or "", tool_calls=calls, parsed_from_text=from_text,
                             prompt_tokens=r.prompt_eval_count or 0, output_tokens=r.eval_count or 0)
