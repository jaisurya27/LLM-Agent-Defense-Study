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
    return WARNING_PATH.read_text(encoding="utf-8").strip()


def format_external_content(content: str, defense: str) -> str:
    """Format one tool result before the model sees it.

    Only warning_boundaries changes the text: it puts a marker line before and
    after the original content, which is kept exactly as it was.
    """
    _check(defense)
    if defense != "warning_boundaries":
        return content
    return f"{BOUNDARY_OPEN}\n{content}\n{BOUNDARY_CLOSE}"
