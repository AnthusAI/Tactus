"""
Human Primitive - Human-in-the-Loop (HITL) operations.

Provides:
- Human.approve(opts) - Request yes/no approval (blocking)
- Human.input(opts) - Request free-form input (blocking)
- Human.review(opts) - Request review with options (blocking)
- Human.notify(opts) - Send notification (non-blocking)
- Human.escalate(opts) - Escalate to human (blocking)
"""

import logging
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


class HumanPrimitive:
    """
    Manages human-in-the-loop operations for procedures.

    Uses a pluggable HITLHandler protocol implementation to manage
    actual human interactions (via CLI, web UI, API, etc.).
    """

    def __init__(self, execution_context, hitl_config: Optional[Dict[str, Any]] = None):
        """
        Initialize Human primitive.

        Args:
            execution_context: ExecutionContext with HITL handler
            hitl_config: Optional HITL declarations from YAML
        """
        self.execution_context = execution_context
        self.hitl_config = hitl_config or {}
        logger.debug("HumanPrimitive initialized")

    def _convert_lua_to_python(self, obj: Any) -> Any:
        """Recursively convert Lua tables to Python dicts."""
        if obj is None:
            return None
        # Check if it's a Lua table (has .items() but not a dict)
        if hasattr(obj, "items") and not isinstance(obj, dict):
            # Convert Lua table to dict
            result = {}
            for key, value in obj.items():
                result[key] = self._convert_lua_to_python(value)
            return result
        elif isinstance(obj, dict):
            # Recursively convert nested dicts
            return {k: self._convert_lua_to_python(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            # Recursively convert lists
            return [self._convert_lua_to_python(item) for item in obj]
        else:
            # Primitive type, return as-is
            return obj

    def approve(self, options: Optional[Dict[str, Any]] = None) -> bool:
        """
        Request yes/no approval from human (BLOCKING).

        Args:
            options: Dict with:
                - message: str - Message to show human
                - context: Dict - Additional context
                - timeout: int - Timeout in seconds (None = no timeout)
                - default: bool - Default if timeout (default: False)
                - config_key: str - Reference to hitl: declaration

        Returns:
            bool - True if approved, False if rejected/timeout

        Example (Lua):
            local approved = Human.approve({
                message = "Deploy to production?",
                context = {environment = "prod"},
                timeout = 3600,
                default = false
            })

            if approved then
                deploy()
            end
        """
        # Convert Lua tables to Python dicts recursively
        opts = self._convert_lua_to_python(options) or {}

        # Check for config reference
        config_key = opts.get("config_key")
        if config_key and config_key in self.hitl_config:
            # Merge config with runtime options (runtime wins)
            config_opts = self.hitl_config[config_key].copy()
            config_opts.update(opts)
            opts = config_opts

        message = opts.get("message", "Approval requested")
        context = opts.get("context", {})
        timeout = opts.get("timeout")
        default = opts.get("default", False)

        logger.info(f"Human approval requested: {message[:50]}...")

        # Delegate to execution context's wait_for_human
        response = self.execution_context.wait_for_human(
            request_type="approval",
            message=message,
            timeout_seconds=timeout,
            default_value=default,
            options=None,
            metadata=context,
        )

        return response.value

    def input(self, options: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Request free-form input from human (BLOCKING).

        Args:
            options: Dict with:
                - message: str - Prompt for human
                - placeholder: str - Input placeholder
                - timeout: int - Timeout in seconds
                - default: str - Default if timeout
                - config_key: str - Reference to hitl: declaration

        Returns:
            str or None - Human's input, or None if timeout with no default

        Example (Lua):
            local topic = Human.input({
                message = "What topic?",
                placeholder = "Enter topic...",
                timeout = 600
            })

            if topic then
                State.set("topic", topic)
            end
        """
        # Convert Lua table to dict if needed
        opts = self._convert_lua_to_python(options) or {}

        # Check for config reference
        config_key = opts.get("config_key")
        if config_key and config_key in self.hitl_config:
            config_opts = self.hitl_config[config_key].copy()
            config_opts.update(opts)
            opts = config_opts

        message = opts.get("message", "Input requested")
        placeholder = opts.get("placeholder", "")
        timeout = opts.get("timeout")
        default = opts.get("default")

        logger.info(f"Human input requested: {message[:50]}...")

        # Delegate to execution context
        response = self.execution_context.wait_for_human(
            request_type="input",
            message=message,
            timeout_seconds=timeout,
            default_value=default,
            options=None,
            metadata={"placeholder": placeholder},
        )

        return response.value

    def review(self, options: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Request human review (BLOCKING).

        Args:
            options: Dict with:
                - message: str - Review prompt
                - artifact: Any - Thing to review
                - artifact_type: str - Type of artifact
                - options: List[str] - Available actions
                - timeout: int - Timeout in seconds
                - config_key: str - Reference to hitl: declaration

        Returns:
            Dict with:
                - decision: str - Selected option
                - edited_artifact: Any - Modified artifact (if edited)
                - feedback: str - Human feedback

        Example (Lua):
            local review = Human.review({
                message = "Review this document",
                artifact = document,
                artifact_type = "document",
                options = {"approve", "edit", "reject"}
            })

            if review.decision == "approve" then
                publish(review.artifact)
            end
        """
        # Convert Lua table to dict if needed
        opts = self._convert_lua_to_python(options) or {}

        # Check for config reference
        config_key = opts.get("config_key")
        if config_key and config_key in self.hitl_config:
            config_opts = self.hitl_config[config_key].copy()
            config_opts.update(opts)
            opts = config_opts

        message = opts.get("message", "Review requested")
        artifact = opts.get("artifact")
        options_list = opts.get("options", ["approve", "reject"])
        artifact_type = opts.get("artifact_type", "artifact")
        timeout = opts.get("timeout")

        logger.info(f"Human review requested: {message[:50]}...")

        # Convert artifact from Lua table to Python dict
        artifact_python = self._convert_lua_to_python(artifact) if artifact is not None else None

        # Convert options list to format expected by protocol: [{label, type}, ...]
        formatted_options = []
        for opt in options_list:
            # If already a dict with label/type, use as-is
            if isinstance(opt, dict) and "label" in opt:
                formatted_options.append(opt)
            # Otherwise treat as string label, default to "action" type
            else:
                formatted_options.append({"label": str(opt).title(), "type": "action"})

        # Delegate to execution context
        response = self.execution_context.wait_for_human(
            request_type="review",
            message=message,
            timeout_seconds=timeout,
            default_value={
                "decision": "reject",
                "edited_artifact": artifact_python,
                "feedback": "",
            },
            options=formatted_options,
            metadata={"artifact": artifact_python, "artifact_type": artifact_type},
        )

        return response.value

    def notify(self, options: Optional[Dict[str, Any]] = None) -> None:
        """
        Send notification to human (NON-BLOCKING).

        Note: In Tactus core, notifications are logged but not sent to HITL handler
        (since they're non-blocking). Implementations that need actual notification
        delivery should use a custom notification system.

        Args:
            options: Dict with:
                - message: str - Notification message (required)
                - level: str - info, warning, error (default: info)

        Example (Lua):
            Human.notify({
                message = "Processing complete",
                level = "info"
            })
        """
        # Convert Lua table to dict if needed
        opts = self._convert_lua_to_python(options) or {}

        message = opts.get("message", "Notification")
        level = opts.get("level", "info")

        logger.info(f"Human notification: [{level}] {message}")

        # In base Tactus, notifications are just logged
        # Implementations can override this to send actual notifications

    def escalate(self, options: Optional[Dict[str, Any]] = None) -> None:
        """
        Escalate to human (BLOCKING).

        Stops workflow execution until human resolves the issue.
        Unlike approve/input/review, escalate has NO timeout - it blocks
        indefinitely until a human manually resumes the procedure.

        Args:
            options: Dict with:
                - message: str - Escalation message
                - context: Dict - Error context
                - severity: str - Severity level (info/warning/error/critical)
                - config_key: str - Reference to hitl: declaration

        Returns:
            None - Execution resumes when human resolves

        Example (Lua):
            if attempts > 3 then
                Human.escalate({
                    message = "Cannot resolve automatically",
                    context = {attempts = attempts, error = last_error},
                    severity = "error"
                })
                -- Workflow continues here after human resolves
            end
        """
        # Convert Lua tables to Python dicts recursively
        opts = self._convert_lua_to_python(options) or {}

        # Check for config reference
        config_key = opts.get("config_key")
        if config_key and config_key in self.hitl_config:
            # Merge config with runtime options (runtime wins)
            config_opts = self.hitl_config[config_key].copy()
            config_opts.update(opts)
            opts = config_opts

        message = opts.get("message", "Escalation required")
        context = opts.get("context", {})
        severity = opts.get("severity", "error")

        logger.warning(f"Human escalation: {message[:50]}... (severity: {severity})")

        # Prepare metadata with severity and context
        metadata = {"severity": severity, "context": context}

        # Delegate to execution context
        # No timeout, no default - blocks until human resolves
        self.execution_context.wait_for_human(
            request_type="escalation",
            message=message,
            timeout_seconds=None,  # No timeout - wait indefinitely
            default_value=None,  # No default - human must resolve
            options=None,
            metadata=metadata,
        )

        logger.info("Human escalation resolved - resuming workflow")

    def __repr__(self) -> str:
        return f"HumanPrimitive(config_keys={list(self.hitl_config.keys())})"
