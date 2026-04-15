import json
import re
from .base_agent import BaseAgent

REVIEWER_SYSTEM = """You are a senior Python code reviewer with expertise in
security, performance, and software design.

Analyze the given code and return ONLY valid JSON with exactly this schema:
{
  "scores": {
    "correctness": <0-10>,
    "security": <0-10>,
    "style": <0-10>,
    "complexity": <0-10>
  },
  "issues": [
    {
      "line": <line_number_int>,
      "severity": "low|medium|high",
      "category": "correctness|security|style|complexity",
      "message": "specific description of the issue"
    }
  ],
  "summary": "one paragraph summary of the overall code quality",
  "recommendations": ["list of the top 3 concrete improvement suggestions"]
}

No preamble. No explanation. Only the JSON object."""


class ReviewerAgent(BaseAgent):
    """
    Reviews generated code and returns structured quality scores.
    Issues include line numbers and severity for precise reporting.
    """

    def __init__(self, api_key: str, model: str = "claude-opus-4-5"):
        super().__init__("Reviewer", REVIEWER_SYSTEM, api_key, model=model)

    def review(self, code_path: str,
               correction_hint: str = "") -> dict:
        """
        Review the code at code_path.
        correction_hint is populated by the Judge on retry runs.
        Returns the parsed review dict.
        """
        code = self.read_file(code_path)
        prompt = f"Review this Python code:\n\n{code}"
        if correction_hint:
            prompt += f"\n\nPrevious review was flagged by the Judge.\n" \
                      f"Issue to address: {correction_hint}"

        raw = self.call(prompt)
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("```").strip()
        return json.loads(raw)
