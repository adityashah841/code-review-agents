import os
import json
from datetime import datetime


def generate_report(result: dict, output_path: str) -> None:
    """
    Convert the pipeline result dict into a clean Markdown report.
    result keys: module_name, raw_spec, spec_contract, code_path,
                 review, test_path, test_stdout, tests_passed,
                 judge_retries, total_input_tokens, total_output_tokens
    """
    review = result["review"]
    scores = review.get("scores", {})
    avg_score = round(sum(scores.values()) / max(len(scores), 1), 1)
    issues = review.get("issues", [])
    high   = [i for i in issues if i.get("severity") == "high"]
    medium = [i for i in issues if i.get("severity") == "medium"]
    low    = [i for i in issues if i.get("severity") == "low"]

    lines = [
        f"# Code Review Report — `{result['module_name']}`",
        f"",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  ",
        f"**Spec:** {result['raw_spec']}  ",
        f"**Tests:** {'PASSED' if result['tests_passed'] else 'FAILED'}  ",
        f"**Judge retries:** {result.get('judge_retries', 0)}  ",
        f"**Tokens used:** {result.get('total_input_tokens', 0)} in / "
        f"{result.get('total_output_tokens', 0)} out  ",
        f"",
        f"---",
        f"",
        f"## Overall score: {avg_score}/10",
        f"",
        f"| Category | Score | Rating |",
        f"|---|---|---|",
    ]

    for category, score in scores.items():
        if score >= 8:
            rating = "Excellent"
        elif score >= 6:
            rating = "Good"
        elif score >= 4:
            rating = "Fair"
        else:
            rating = "Needs work"
        lines.append(f"| {category.capitalize()} | {score}/10 | {rating} |")

    lines += [
        f"",
        f"---",
        f"",
        f"## Summary",
        f"",
        review.get("summary", "No summary provided."),
        f"",
        f"## Issues found",
        f"",
    ]

    if not issues:
        lines.append("No issues found.")
    else:
        if high:
            lines.append("### High severity")
            for i in high:
                lines.append(f"- **Line {i.get('line','?')}** "
                              f"[{i.get('category','general')}]: "
                              f"{i.get('message','')}")
        if medium:
            lines.append("\n### Medium severity")
            for i in medium:
                lines.append(f"- **Line {i.get('line','?')}** "
                              f"[{i.get('category','general')}]: "
                              f"{i.get('message','')}")
        if low:
            lines.append("\n### Low severity")
            for i in low:
                lines.append(f"- **Line {i.get('line','?')}** "
                              f"[{i.get('category','general')}]: "
                              f"{i.get('message','')}")

    recommendations = review.get("recommendations", [])
    if recommendations:
        lines += ["", "## Recommendations", ""]
        for r in recommendations:
            lines.append(f"- {r}")

    lines += [
        f"",
        f"---",
        f"",
        f"## Test results",
        f"",
        f"**Status:** {'PASSED' if result['tests_passed'] else 'FAILED'}",
        f"",
        f"```",
        result.get("test_stdout", "No test output."),
        f"```",
        f"",
        f"---",
        f"",
        f"## Expanded spec contract",
        f"",
        f"```json",
        json.dumps(result.get("spec_contract", {}), indent=2),
        f"```",
    ]

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w") as f:
        f.write("\n".join(lines))
