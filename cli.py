import os
import sys
import asyncio
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm
from rich import print as rprint

from orchestrator import run_pipeline
from report_generator import generate_report
from history import get_history

console = Console()


def validate_api_key(api_key: str) -> None:
    """Validate API key format and fail fast with a clear message."""
    if not api_key:
        raise click.UsageError(
            "An Anthropic API key is required.\n"
            "Pass it with --api-key or set ANTHROPIC_API_KEY.\n"
            "Get a key at: https://console.anthropic.com"
        )
    if not api_key.startswith("sk-ant-"):
        raise click.UsageError(
            "The key does not look valid (must start with 'sk-ant-').\n"
            "Check your key at: https://console.anthropic.com"
        )


@click.group()
def cli():
    """
    code-review-agents — multi-agent Python code review.

    Three AI agents (Coder, Reviewer, Tester) collaborate under the
    supervision of a Judge agent to generate, review, and test Python
    code from a plain-English spec.
    """
    pass


@cli.command()
@click.option(
    "--spec", "-s",
    required=True,
    help='Plain-English function spec. e.g. "sort a list of integers"',
)
@click.option(
    "--name", "-n",
    default="module",
    show_default=True,
    help="Output module name (used as filename, no .py extension)",
)
@click.option(
    "--output", "-o",
    default="reports/review.md",
    show_default=True,
    help="Path to write the Markdown report",
)
@click.option(
    "--api-key", "-k",
    default=lambda: os.getenv("ANTHROPIC_API_KEY", ""),
    hide_input=True,
    help="Anthropic API key (or set ANTHROPIC_API_KEY env var)",
)
@click.option(
    "--stream",
    is_flag=True,
    default=False,
    help="Stream the Coder agent output token-by-token",
)
@click.option(
    "--yes", "-y",
    is_flag=True,
    default=False,
    help="Skip the spec confirmation prompt",
)
def review(spec, name, output, api_key, stream, yes):
    """Run the full multi-agent review pipeline on a spec."""

    validate_api_key(api_key)

    console.print()
    console.print(Panel.fit(
        f"[bold]code-review-agents[/bold]\n"
        f"Spec: [italic]{spec}[/italic]",
        border_style="dim",
    ))
    console.print()

    # Run the pipeline
    with console.status("[bold green]Running pipeline...[/bold green]",
                         spinner="dots"):
        result = asyncio.run(
            run_pipeline(
                raw_spec=spec,
                module_name=name,
                api_key=api_key,
                stream_coder=stream,
                console=console,
            )
        )

    # Show the expanded spec and ask for post-hoc confirmation
    if not yes:
        contract = result["spec_contract"]
        console.print("\n[bold]Expanded spec contract:[/bold]")
        console.print(f"  Function : [cyan]{contract.get('function_name')}[/cyan]")
        console.print(f"  Returns  : {contract.get('returns', {}).get('type')}")
        console.print(f"  Example  : {contract.get('example_call')}")
        console.print()

    # Print rich score table
    scores = result["review"].get("scores", {})
    table = Table(title="Review scores", show_header=True,
                  header_style="bold")
    table.add_column("Category", style="dim")
    table.add_column("Score", justify="right")
    table.add_column("Rating")

    for category, score in scores.items():
        if score >= 8:
            rating, color = "Excellent", "green"
        elif score >= 6:
            rating, color = "Good", "yellow"
        elif score >= 4:
            rating, color = "Fair", "yellow"
        else:
            rating, color = "Needs work", "red"
        table.add_row(
            category.capitalize(),
            f"{score}/10",
            f"[{color}]{rating}[/{color}]",
        )

    console.print(table)
    console.print()

    # Print test result
    status_color = "green" if result["tests_passed"] else "red"
    status_text  = "PASSED" if result["tests_passed"] else "FAILED"
    console.print(
        f"Tests: [{status_color}]{status_text}[/{status_color}]  |  "
        f"Judge retries: {result['judge_retries']}  |  "
        f"Tokens: {result['total_input_tokens']}in / "
        f"{result['total_output_tokens']}out"
    )
    console.print()

    # Write report
    generate_report(result, output)
    console.print(f"[green]Report saved to[/green] {output}")
    console.print()


@cli.command()
@click.option("--limit", "-n", default=20, show_default=True,
              help="Number of recent runs to show")
def history(limit):
    """Show history of previous pipeline runs."""
    runs = get_history(limit)
    if not runs:
        console.print("[dim]No runs recorded yet.[/dim]")
        return

    table = Table(title=f"Last {min(limit, len(runs))} runs",
                  show_header=True, header_style="bold")
    table.add_column("ID",      style="dim", justify="right")
    table.add_column("Time",    style="dim")
    table.add_column("Spec",    max_width=35)
    table.add_column("Module",  style="cyan")
    table.add_column("Score",   justify="right")
    table.add_column("Tests")
    table.add_column("Retries", justify="right")
    table.add_column("Tokens",  justify="right")

    for r in runs:
        tests_text = (
            "[green]PASS[/green]" if r["tests_passed"]
            else "[red]FAIL[/red]"
        )
        tokens = (r["total_input_tokens"] or 0) + (r["total_output_tokens"] or 0)
        table.add_row(
            str(r["id"]),
            r["timestamp"][:16],
            r["raw_spec"][:35],
            r["module_name"],
            f"{r['avg_score']:.1f}/10",
            tests_text,
            str(r["judge_retries"]),
            f"{tokens:,}",
        )

    console.print(table)


if __name__ == "__main__":
    cli()
