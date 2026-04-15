import os
import click


def validate_api_key(api_key: str) -> None:
    """
    Validate the API key format before any agents run.
    Raises click.UsageError with a clear message on failure.
    """
    if not api_key:
        raise click.UsageError(
            "An Anthropic API key is required.\n"
            "Pass it with --api-key or set the ANTHROPIC_API_KEY "
            "environment variable.\n"
            "Get a key at: https://console.anthropic.com"
        )
    if not api_key.startswith("sk-ant-"):
        raise click.UsageError(
            "The provided key does not look like a valid Anthropic API key.\n"
            "Keys start with 'sk-ant-'. Check your key at "
            "console.anthropic.com"
        )
