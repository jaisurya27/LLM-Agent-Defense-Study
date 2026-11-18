"""Defense configurations (owner: De).

Starting version written from the team work plan so the runner can be built
and tested. De owns the wording and placement; change them here and in
prompts/warning.txt, not in the runner.

These two functions are project conventions, not AgentDojo APIs.
"""

from pathlib import Path

DEFENSES = ("default", "warning", "warning_boundaries")

WARNING_PATH = Path(__file__).resolve().parent.parent / "prompts" / "warning.txt"
BOUNDARY_OPEN = "<external_content>"
BOUNDARY_CLOSE = "</external_content>"


def _check(defense: str) -> None:
    if defense not in DEFENSES:
        raise ValueError(f"Unknown defense {defense!r}. Expected one of {DEFENSES}.")


def get_defense_instruction(defense: str) -> str:
    """Text appended to the system message. Empty for the default agent."""
    _check(defense)
    if defense == "default":
        return ""
    with WARNING_PATH.open(encoding="utf-8", newline="") as prompt_file:
        warning = prompt_file.read()
    return warning.removesuffix("\n").removesuffix("\r")


def format_external_content(content: str, defense: str) -> str:
    """Format one tool result before the model sees it.

    Only warning_boundaries changes the text: it puts a marker line before and
    after the original content, which is kept exactly as it was.
    """
    _check(defense)
    if not isinstance(content, str):
        raise TypeError("content must be a string; select tool-response text first")
    if defense != "warning_boundaries":
        return content
    return f"{BOUNDARY_OPEN}\n{content}\n{BOUNDARY_CLOSE}"
