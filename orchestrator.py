import asyncio
import subprocess
import sys
import os
from agents import (
    SpecAgent, CoderAgent, ReviewerAgent, TesterAgent, JudgeAgent
)
from history import save_run


async def run_pipeline(
    raw_spec: str,
    module_name: str,
    api_key: str,
    stream_coder: bool = False,
    console=None,
) -> dict:
    """
    Full pipeline:
    1. Spec agent expands raw spec to contract
    2. Coder generates code
    3. Reviewer + Tester run in parallel
    4. Tests are executed
    5. Judge evaluates all outputs
    6. On Judge failure: targeted agent retries (max JudgeAgent.MAX_RETRIES)
    7. Final result assembled and saved to history

    Returns the complete result dict for report_generator.
    """

    def log(msg: str):
        if console:
            console.log(msg)
        else:
            print(msg)

    # --- Instantiate agents ---
    spec_agent     = SpecAgent(api_key)
    coder_agent    = CoderAgent(api_key)
    reviewer_agent = ReviewerAgent(api_key)
    tester_agent   = TesterAgent(api_key)
    judge_agent    = JudgeAgent(api_key)

    # --- Step 1: Spec expansion ---
    log("[Spec] Expanding spec contract...")
    spec_contract = await asyncio.to_thread(spec_agent.expand, raw_spec)

    # --- Step 2: Coder ---
    log("[Coder] Generating code...")
    code_path = await asyncio.to_thread(
        coder_agent.generate, spec_contract, module_name, stream_coder, ""
    )

    judge_retries = 0
    coder_hint = reviewer_hint = tester_hint = ""

    for attempt in range(JudgeAgent.MAX_RETRIES + 1):

        # --- Step 3: Retry coder if Judge flagged it ---
        if attempt > 0 and coder_hint:
            log(f"[Coder] Retry {attempt}/{JudgeAgent.MAX_RETRIES} — {coder_hint}")
            code_path = await asyncio.to_thread(
                coder_agent.generate, spec_contract, module_name,
                False, coder_hint
            )
            coder_hint = ""

        # --- Step 4: Reviewer + Tester in parallel ---
        log("[Reviewer + Tester] Running in parallel...")
        review_result, test_path = await asyncio.gather(
            asyncio.to_thread(
                reviewer_agent.review, code_path, reviewer_hint
            ),
            asyncio.to_thread(
                tester_agent.generate_tests, code_path, module_name,
                spec_contract, tester_hint
            ),
        )
        reviewer_hint = tester_hint = ""

        # --- Step 5: Execute tests ---
        log("[Runner] Executing pytest...")
        sys.path.insert(0, os.getcwd())
        test_result = subprocess.run(
            [sys.executable, "-m", "pytest", test_path,
             "--tb=short", "-q", "--no-header"],
            capture_output=True,
            text=True,
            cwd=".",
        )
        test_stdout  = test_result.stdout + test_result.stderr
        tests_passed = test_result.returncode == 0

        # --- Step 6: Judge evaluation ---
        log("[Judge] Evaluating all outputs...")
        verdict = await asyncio.to_thread(
            judge_agent.evaluate,
            spec_contract, code_path, review_result,
            test_path, test_stdout, test_result.returncode,
        )

        if verdict["overall_pass"]:
            log("[Judge] All agents passed.")
            break

        # Identify which agents need retries
        failed_agents = [
            name for name, info in verdict["agents"].items()
            if not info["pass"]
        ]
        log(f"[Judge] Failed agents: {failed_agents}. "
            f"Retry {attempt + 1}/{JudgeAgent.MAX_RETRIES}")

        if attempt < JudgeAgent.MAX_RETRIES:
            judge_retries += 1
            agents_info = verdict["agents"]
            if not agents_info["coder"]["pass"]:
                coder_hint = agents_info["coder"]["reason"] or "Fix the code"
            if not agents_info["reviewer"]["pass"]:
                reviewer_hint = agents_info["reviewer"]["reason"] or "Fix the review"
            if not agents_info["tester"]["pass"]:
                tester_hint = agents_info["tester"]["reason"] or "Fix the tests"
        else:
            log("[Judge] Max retries reached. Proceeding with best available outputs.")

    # --- Step 7: Aggregate token usage ---
    all_agents = [spec_agent, coder_agent, reviewer_agent,
                  tester_agent, judge_agent]
    total_input  = sum(a.total_input_tokens  for a in all_agents)
    total_output = sum(a.total_output_tokens for a in all_agents)

    result = {
        "module_name":          module_name,
        "raw_spec":             raw_spec,
        "spec_contract":        spec_contract,
        "code_path":            code_path,
        "review":               review_result,
        "test_path":            test_path,
        "test_stdout":          test_stdout,
        "tests_passed":         tests_passed,
        "judge_verdict":        verdict,
        "judge_retries":        judge_retries,
        "total_input_tokens":   total_input,
        "total_output_tokens":  total_output,
    }

    # --- Step 8: Persist to history ---
    scores = review_result.get("scores", {})
    avg_score = sum(scores.values()) / max(len(scores), 1)
    save_run(
        raw_spec=raw_spec,
        module_name=module_name,
        avg_score=avg_score,
        tests_passed=tests_passed,
        judge_retries=judge_retries,
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        report_path="",  # updated by CLI after report is written
    )

    return result
