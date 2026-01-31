"""
Tactus exception classes.

All custom exceptions raised by the Tactus runtime.
"""


class TactusRuntimeError(Exception):
    """Base exception for all Tactus runtime errors."""

    pass


class ProcedureWaitingForHuman(Exception):
    """
    Raised to exit workflow when waiting for human response.

    In execution contexts that support exit-and-resume, this signals:
    1. Update Procedure status to 'WAITING_FOR_HUMAN'
    2. Save the pending message ID
    3. Exit cleanly
    4. Wait for resume trigger
    """

    message_template = (
        "Procedure {procedure_id} waiting for human response to message {pending_message_id}"
    )

    procedure_id: str
    pending_message_id: str

    def __init__(self, procedure_id: str, pending_message_id: str):
        self.procedure_id = procedure_id
        self.pending_message_id = pending_message_id
        super().__init__(
            self.message_template.format(
                procedure_id=procedure_id, pending_message_id=pending_message_id
            )
        )


class ProcedureConfigError(Exception):
    """Raised when procedure configuration is invalid."""

    pass


class LuaSandboxError(Exception):
    """Raised when Lua sandbox setup or execution fails."""

    pass


class OutputValidationError(Exception):
    """Raised when workflow output doesn't match schema."""

    pass


class StorageError(TactusRuntimeError):
    """Raised when storage backend operations fail."""

    pass


class HITLError(TactusRuntimeError):
    """Raised when HITL handler operations fail."""

    pass


class ChatRecorderError(TactusRuntimeError):
    """Raised when chat recorder operations fail."""

    pass
