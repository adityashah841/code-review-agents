import anthropic
import time
import os
import ast
from typing import Optional


class BaseAgent:
    """
    Shared base class for all agents.
    Wraps the Anthropic API with retry logic, streaming support,
    and file I/O helpers. API key is passed at construction time —
    never read from environment or hardcoded.
    """

    def __init__(self, name: str, system_prompt: str, api_key: str,
                 model: str = "claude-opus-4-5"):
        self.name = name
        self.system_prompt = system_prompt
        self.model = model
        self.client = anthropic.Anthropic(api_key=api_key)
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def call(self, user_msg: str, max_retries: int = 3,
             stream: bool = False) -> str:
        """
        Call the model with retry logic and optional streaming.
        Accumulates token usage across all calls.
        """
        for attempt in range(max_retries):
            try:
                if stream:
                    return self._call_streaming(user_msg)
                else:
                    return self._call_blocking(user_msg)
            except anthropic.APIStatusError as e:
                if e.status_code == 401:
                    raise ValueError(
                        "Invalid API key. Check your key at "
                        "console.anthropic.com"
                    ) from e
                if attempt == max_retries - 1:
                    raise
                wait = 2 ** attempt
                print(f"[{self.name}] API error, retrying in {wait}s...")
                time.sleep(wait)
            except anthropic.APIConnectionError:
                if attempt == max_retries - 1:
                    raise
                time.sleep(2 ** attempt)

    def _call_blocking(self, user_msg: str) -> str:
        message = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=self.system_prompt,
            messages=[{"role": "user", "content": user_msg}],
        )
        self.total_input_tokens += message.usage.input_tokens
        self.total_output_tokens += message.usage.output_tokens
        return message.content[0].text

    def _call_streaming(self, user_msg: str) -> str:
        full_text = ""
        with self.client.messages.stream(
            model=self.model,
            max_tokens=4096,
            system=self.system_prompt,
            messages=[{"role": "user", "content": user_msg}],
        ) as stream:
            for text in stream.text_stream:
                print(text, end="", flush=True)
                full_text += text
            print()
            usage = stream.get_final_message().usage
            self.total_input_tokens += usage.input_tokens
            self.total_output_tokens += usage.output_tokens
        return full_text

    def write_file(self, filename: str, content: str) -> str:
        """Write content to workspace/ and return the full path."""
        os.makedirs("workspace", exist_ok=True)
        path = f"workspace/{filename}"
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def read_file(self, path: str) -> str:
        """Read a file and return its content."""
        with open(path, encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def validate_python_syntax(code: str) -> tuple[bool, str]:
        """
        Parse Python code with ast.parse().
        Returns (True, "") on success or (False, error_message) on failure.
        Free — no API call required.
        """
        try:
            ast.parse(code)
            return True, ""
        except SyntaxError as e:
            return False, f"SyntaxError at line {e.lineno}: {e.msg}"
