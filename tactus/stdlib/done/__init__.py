"""
Standard 'done' tool for Tactus.

This tool signals task completion and is the most commonly used tool
in Tactus procedures.
"""

from typing import Optional


def done(reason: Optional[str] = None) -> dict:
    """
    Signal task completion.

    This tool is used by agents to indicate they have completed their task.
    It's the standard way for procedures to terminate successfully.

    Args:
        reason: Optional explanation of why the task is complete.
                Can be used to provide context about what was accomplished.

    Returns:
        A dictionary with:
        - status: Always "completed"
        - reason: The provided reason or a default message
        - tool: Always "done" to identify this was a done tool call

    Examples:
        >>> done()
        {'status': 'completed', 'reason': 'Task completed', 'tool': 'done'}

        >>> done("Successfully analyzed all data")
        {'status': 'completed', 'reason': 'Successfully analyzed all data', 'tool': 'done'}
    """
    return {"status": "completed", "reason": reason or "Task completed", "tool": "done"}


# Alias for backward compatibility if needed
__all__ = ["done"]
