"""
Human Primitive - Human-in-the-Loop (HITL) operations.

Provides:
- Human.approve(opts) - Request yes/no approval (blocking)
- Human.input(opts) - Request free-form input (blocking)
- Human.select(opts) - Request selection from options (blocking)
- Human.multiple(items) - Request multiple inputs in one interaction (blocking)
- Human.review(opts) - Request review with options (blocking)
- Human.notify(opts) - Send notification (non-blocking)
- Human.escalate(opts) - Escalate to human (blocking)
- Human.custom(opts) - Request custom component interaction (blocking)

Deprecated:
- Human.inputs(items) - Use Human.multiple() instead
"""

import logging
from typing import Any, Dict, List, Optional

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
        """Recursively convert Lua tables to Python dicts or lists."""
        if obj is None:
            return None
        # Check if it's a Lua table (has .items() but not a dict)
        if hasattr(obj, "items") and not isinstance(obj, dict):
            # Get all items from the Lua table
            items = list(obj.items())

            # Check if this is an array-like table (numeric keys starting from 1)
            if items and all(isinstance(k, int) for k, v in items):
                # Sort by key and extract values to create a Python list
                sorted_items = sorted(items, key=lambda x: x[0])
                # Check if keys are consecutive starting from 1
                if [k for k, v in sorted_items] == list(range(1, len(sorted_items) + 1)):
                    return [self._convert_lua_to_python(v) for k, v in sorted_items]

            # Otherwise, convert to dict (string keys or mixed)
            result = {}
            for key, value in items:
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
            options: Dict with options OR string message for convenience
                - message: str - Message to show human
                - context: Dict - Additional context
                - timeout: int - Timeout in seconds (None = no timeout)
                - default: bool - Default if timeout (default: False)
                - config_key: str - Reference to hitl: declaration

        Returns:
            bool - True if approved, False if rejected/timeout

        Example (Lua):
            -- Simple form (just message string)
            local approved = Human.approve("Deploy to production?")

            -- Full form (with options)
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

        # Support string message shorthand: Human.approve("message")
        if isinstance(opts, str):
            opts = {"message": opts}

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

        # CRITICAL: Wrap HITL call in checkpoint for transparent durability
        # This allows kill/resume to work - procedure can be restarted and will resume from this point
        logger.debug("[CHECKPOINT] Creating checkpoint for Human.approve(), type=hitl_approval")

        def checkpoint_fn():
            return self.execution_context.wait_for_human(
                request_type="approval",
                message=message,
                timeout_seconds=timeout,
                default_value=default,
                options=None,
                metadata=context,
            )

        response = self.execution_context.checkpoint(checkpoint_fn, "hitl_approval")
        logger.debug(f"[CHECKPOINT] Human.approve() checkpoint completed, response={response}")

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

        # CRITICAL: Wrap HITL call in checkpoint for transparent durability
        def checkpoint_fn():
            return self.execution_context.wait_for_human(
                request_type="input",
                message=message,
                timeout_seconds=timeout,
                default_value=default,
                options=None,
                metadata={"placeholder": placeholder},
            )

        response = self.execution_context.checkpoint(checkpoint_fn, "hitl_input")

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

        # CRITICAL: Wrap HITL call in checkpoint for transparent durability
        def checkpoint_fn():
            return self.execution_context.wait_for_human(
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

        response = self.execution_context.checkpoint(checkpoint_fn, "hitl_review")

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

        # CRITICAL: Wrap HITL call in checkpoint for transparent durability
        def checkpoint_fn():
            return self.execution_context.wait_for_human(
                request_type="escalation",
                message=message,
                timeout_seconds=None,  # No timeout - wait indefinitely
                default_value=None,  # No default - human must resolve
                options=None,
                metadata=metadata,
            )

        self.execution_context.checkpoint(checkpoint_fn, "hitl_escalation")

        logger.info("Human escalation resolved - resuming workflow")

    def select(self, options: Optional[Dict[str, Any]] = None) -> Any:
        """
        Request selection from options (BLOCKING).

        Supports both single-select (radio buttons/dropdown) and multi-select (checkboxes).

        Args:
            options: Dict with:
                - message: str - Prompt for human
                - options: List[str] or List[Dict] - Available choices
                - mode: str - "single" (default) or "multiple"
                - style: str - UI hint: "radio", "dropdown", "checkbox" (optional)
                - min: int - Minimum selections required (for multiple mode)
                - max: int - Maximum selections allowed (for multiple mode)
                - default: Any - Default selection(s) if timeout
                - timeout: int - Timeout in seconds
                - config_key: str - Reference to hitl: declaration

        Returns:
            For single mode: str - Selected option value
            For multiple mode: List[str] - Selected option values

        Example (Lua):
            -- Single select (radio buttons)
            local target = Human.select({
                message = "Choose deployment target",
                options = {"staging", "production", "development"},
                mode = "single",
                style = "radio"
            })

            -- Multi-select (checkboxes)
            local features = Human.select({
                message = "Which features to enable?",
                options = {"dark_mode", "notifications", "analytics"},
                mode = "multiple",
                min = 1,
                max = 2
            })
        """
        # Convert Lua tables to Python dicts recursively
        opts = self._convert_lua_to_python(options) or {}

        # Check for config reference
        config_key = opts.get("config_key")
        if config_key and config_key in self.hitl_config:
            config_opts = self.hitl_config[config_key].copy()
            config_opts.update(opts)
            opts = config_opts

        message = opts.get("message", "Selection required")
        options_list = opts.get("options", [])
        mode = opts.get("mode", "single")
        style = opts.get("style")  # UI hint: radio, dropdown, checkbox
        min_selections = opts.get("min", 1 if mode == "multiple" else None)
        max_selections = opts.get("max")
        timeout = opts.get("timeout")
        default = opts.get("default", [] if mode == "multiple" else None)

        logger.info(f"Human selection requested ({mode}): {message[:50]}...")

        # Convert options list to format expected by protocol: [{label, value}, ...]
        formatted_options = []
        for opt in options_list:
            if isinstance(opt, dict) and "label" in opt:
                # Already formatted: {label: "...", value: "..."}
                formatted_options.append(opt)
            elif isinstance(opt, dict) and "value" in opt:
                # Has value but no label - use value as label
                formatted_options.append({"label": str(opt["value"]), "value": opt["value"]})
            else:
                # Simple string - use as both label and value
                formatted_options.append({"label": str(opt), "value": opt})

        # Build metadata with select-specific fields
        metadata = {
            "mode": mode,
            "min": min_selections,
            "max": max_selections,
        }
        if style:
            metadata["style"] = style

        # CRITICAL: Wrap HITL call in checkpoint for transparent durability
        def checkpoint_fn():
            return self.execution_context.wait_for_human(
                request_type="select",
                message=message,
                timeout_seconds=timeout,
                default_value=default,
                options=formatted_options,
                metadata=metadata,
            )

        response = self.execution_context.checkpoint(checkpoint_fn, "hitl_select")

        return response.value

    def upload(self, options: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Request file upload from human (BLOCKING).

        Files are stored locally on the filesystem. The response contains
        the file path and metadata, not the file contents.

        Args:
            options: Dict with:
                - message: str - Upload prompt
                - accept: str or List[str] - Accepted file types (e.g., ".pdf,.doc" or ["image/*"])
                - max_size: str or int - Maximum file size (e.g., "10MB" or 10485760)
                - multiple: bool - Allow multiple files (default: False)
                - timeout: int - Timeout in seconds
                - config_key: str - Reference to hitl: declaration

        Returns:
            Dict with file info (or List[Dict] if multiple=True):
                - path: str - Local filesystem path to uploaded file
                - name: str - Original filename
                - size: int - File size in bytes
                - mime_type: str - MIME type of file

            Returns None if timeout with no default.

        Example (Lua):
            -- Single file upload
            local file = Human.upload({
                message = "Upload your document",
                accept = ".pdf,.doc,.docx",
                max_size = "10MB"
            })

            if file then
                print("Uploaded: " .. file.name)
                print("Path: " .. file.path)
                print("Size: " .. file.size .. " bytes")
            end

            -- Multiple file upload
            local images = Human.upload({
                message = "Upload images",
                accept = "image/*",
                multiple = true,
                max_size = "5MB"
            })

            for _, img in ipairs(images or {}) do
                print("Image: " .. img.name)
            end
        """
        # Convert Lua tables to Python dicts recursively
        opts = self._convert_lua_to_python(options) or {}

        # Check for config reference
        config_key = opts.get("config_key")
        if config_key and config_key in self.hitl_config:
            config_opts = self.hitl_config[config_key].copy()
            config_opts.update(opts)
            opts = config_opts

        message = opts.get("message", "File upload requested")
        accept = opts.get("accept")  # File type filter
        max_size = opts.get("max_size")  # Size limit
        multiple = opts.get("multiple", False)
        timeout = opts.get("timeout")

        logger.info(f"Human file upload requested: {message[:50]}...")

        # Normalize accept to list
        if isinstance(accept, str):
            accept = [a.strip() for a in accept.split(",")]

        # Normalize max_size to bytes
        if isinstance(max_size, str):
            max_size = self._parse_size(max_size)

        # Build metadata with upload-specific fields
        metadata = {
            "accept": accept,
            "max_size": max_size,
            "multiple": multiple,
        }

        # CRITICAL: Wrap HITL call in checkpoint for transparent durability
        def checkpoint_fn():
            return self.execution_context.wait_for_human(
                request_type="upload",
                message=message,
                timeout_seconds=timeout,
                default_value=None,
                options=None,
                metadata=metadata,
            )

        response = self.execution_context.checkpoint(checkpoint_fn, "hitl_upload")

        return response.value

    def _parse_size(self, size_str: str) -> int:
        """Parse human-readable size string to bytes."""
        size_str = size_str.strip().upper()
        multipliers = {
            "B": 1,
            "KB": 1024,
            "MB": 1024 * 1024,
            "GB": 1024 * 1024 * 1024,
        }
        for suffix, multiplier in multipliers.items():
            if size_str.endswith(suffix):
                try:
                    return int(float(size_str[: -len(suffix)].strip()) * multiplier)
                except ValueError:
                    pass
        # Try parsing as raw number
        try:
            return int(size_str)
        except ValueError:
            logger.warning(f"Could not parse size '{size_str}', using default")
            return 10 * 1024 * 1024  # Default 10MB

    def inputs(self, items: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Request multiple inputs from human in a single interaction (BLOCKING).

        DEPRECATED: Use Human.multiple() instead for clearer naming.
        This method will be removed in a future version.

        Presents inputs as tabs in the UI, allowing the human to fill them all
        before submitting a single response.

        Args:
            items: List of input items, each with:
                - id: str - Unique ID for this item (required)
                - label: str - Short label for tabs (required)
                - type: str - Request type: "approval", "input", "select", etc. (required)
                - message: str - Prompt for this input (required)
                - options: List - Options for select/review types
                - required: bool - Whether this input is required (default: True)
                - metadata: Dict - Type-specific metadata
                - timeout: int - Timeout in seconds
                - default: Any - Default value

        Returns:
            Dict keyed by item ID with response values:
                {
                    "target": "production",
                    "confirm": True,
                    "notes": "Deploy notes..."
                }

        Example (Lua):
            local responses = Human.inputs({
                {
                    id = "target",
                    label = "Target",
                    type = "select",
                    message = "Which environment?",
                    options = {"staging", "production"}
                },
                {
                    id = "confirm",
                    label = "Confirm",
                    type = "approval",
                    message = "Are you sure?"
                },
                {
                    id = "notes",
                    label = "Notes",
                    type = "input",
                    message = "Any notes?",
                    required = false
                }
            })

            if responses.confirm then
                deploy(responses.target, responses.notes)
            end
        """
        # Deprecation warning
        logger.warning(
            "Human.inputs() is deprecated. Use Human.multiple() instead for clearer naming. "
            "This method will be removed in a future version."
        )

        # Convert Lua tables to Python dicts recursively
        logger.debug(f"Human.inputs() called with items type: {type(items)}")
        items_list = self._convert_lua_to_python(items) or []
        logger.debug(
            f"Converted to items_list, length: {len(items_list)}, type: {type(items_list)}"
        )

        if not items_list:
            raise ValueError("Human.inputs() requires at least one item")

        # Validate items
        seen_ids = set()
        for idx, item in enumerate(items_list):
            logger.debug(
                f"Validating item {idx}: type={type(item)}, keys={list(item.keys()) if isinstance(item, dict) else 'NOT A DICT'}"
            )

            # Ensure item is a dict
            if not isinstance(item, dict):
                raise ValueError(
                    f"Item {idx} is not a dictionary (got {type(item).__name__}): {item}"
                )

            # Validate required fields
            if "id" not in item:
                raise ValueError("Each item must have an 'id' field")
            if "label" not in item:
                raise ValueError("Each item must have a 'label' field")
            if "type" not in item:
                raise ValueError("Each item must have a 'type' field")
            if "message" not in item:
                raise ValueError("Each item must have a 'message' field")

            # Check for duplicate IDs
            item_id = item["id"]
            if item_id in seen_ids:
                raise ValueError(f"Duplicate item ID: {item_id}")
            seen_ids.add(item_id)

        logger.info(f"Human inputs requested: {len(items_list)} items")

        # Build ControlRequestItem list
        from tactus.protocols.control import ControlRequestItem

        request_items = []
        for item in items_list:
            # Convert options if present
            options_list = item.get("options", [])
            formatted_options = []
            for opt in options_list:
                if isinstance(opt, dict) and "label" in opt:
                    formatted_options.append(opt)
                elif isinstance(opt, dict) and "value" in opt:
                    formatted_options.append({"label": str(opt["value"]), "value": opt["value"]})
                else:
                    formatted_options.append({"label": str(opt), "value": opt})

            # Build metadata
            metadata = item.get("metadata", {})

            # Create ControlRequestItem
            request_item = ControlRequestItem(
                item_id=item["id"],
                label=item["label"],
                request_type=item["type"],
                message=item["message"],
                options=formatted_options,
                default_value=item.get("default"),
                required=item.get("required", True),
                metadata=metadata,
            )
            request_items.append(request_item)

        # CRITICAL: Wrap HITL call in checkpoint for transparent durability
        def checkpoint_fn():
            return self.execution_context.wait_for_human(
                request_type="inputs",
                message=f"Multiple inputs requested ({len(items_list)} items)",
                timeout_seconds=None,  # Individual items can have timeouts
                default_value={},
                options=None,
                metadata={"items": [item.model_dump() for item in request_items]},
            )

        response = self.execution_context.checkpoint(checkpoint_fn, "hitl_inputs")

        # Response value should be a dict keyed by item ID
        result = response.value if isinstance(response.value, dict) else {}

        # Convert Python lists to Lua tables for nested values
        # This is needed when frontend returns arrays (e.g., multi-select results)
        lua_runtime = self.execution_context.lua_sandbox.lua
        converted_result = {}
        for key, value in result.items():
            if isinstance(value, list):
                # Convert Python list to Lua table
                converted_result[key] = lua_runtime.table_from(value)
            else:
                converted_result[key] = value

        return lua_runtime.table_from(converted_result)

    def multiple(self, items: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Request multiple inputs from human in a single interaction (BLOCKING).

        This is the preferred method name for collecting multiple inputs.
        Use this instead of inputs() for clearer intent.

        Presents inputs in a unified UI (inline or modal), allowing the human to fill
        them all before submitting a single response.

        Args:
            items: List of input items, each with:
                - id: str - Unique ID for this item (required)
                - label: str - Short label for tabs (required)
                - type: str - Request type: "approval", "input", "select", etc. (required)
                - message: str - Prompt for this input (required)
                - options: List - Options for select/review types
                - required: bool - Whether this input is required (default: True)
                - metadata: Dict - Type-specific metadata
                - timeout: int - Timeout in seconds
                - default: Any - Default value

        Returns:
            Dict keyed by item ID with response values:
                {
                    "target": "production",
                    "confirm": True,
                    "notes": "Deploy notes..."
                }

        Example (Lua):
            local responses = Human.multiple({
                {
                    id = "target",
                    label = "Target",
                    type = "select",
                    message = "Which environment?",
                    options = {"staging", "production"}
                },
                {
                    id = "confirm",
                    label = "Confirm",
                    type = "approval",
                    message = "Are you sure?"
                },
                {
                    id = "notes",
                    label = "Notes",
                    type = "input",
                    message = "Any notes?",
                    required = false
                }
            })

            if responses.confirm then
                deploy(responses.target, responses.notes)
            end
        """
        return self.inputs(items)

    def custom(self, options: Optional[Dict[str, Any]] = None) -> Any:
        """
        Request custom component interaction from human (BLOCKING).

        Renders a custom UI component specified by metadata.component_type.
        The component receives all metadata and can return arbitrary values.

        Args:
            options: Dict with:
                - component_type: str - Which custom component to render (required)
                - message: str - Message to display (required)
                - data: Dict - Component-specific data (images, options, etc.)
                - actions: List[Dict] - Optional action buttons
                - timeout: int - Timeout in seconds
                - default: Any - Default value if timeout
                - config_key: str - Reference to hitl: declaration

        Returns:
            Any - Value returned by the custom component
                  Could be a simple value (string, dict) or complex object
                  depending on the component implementation

        Example (Lua):
            local result = Human.custom({
                component_type = "image-selector",
                message = "Select your favorite image",
                data = {
                    images = {
                        {url = "https://...", label = "Option 1"},
                        {url = "https://...", label = "Option 2"}
                    }
                },
                actions = {
                    {id = "regenerate", label = "Regenerate", style = "secondary"}
                }
            })

            if result.action == "regenerate" then
                -- User clicked regenerate
                return {regenerate = true}
            else
                -- User selected an image
                return {selected_url = result}
            end
        """
        if not isinstance(options, dict):
            raise TypeError("custom() requires a dict argument with component_type and message")

        component_type = options.get("component_type")
        if not component_type:
            raise ValueError("custom() requires 'component_type' field in options")

        message = options.get("message")
        if not message:
            raise ValueError("custom() requires 'message' field in options")

        # Extract parameters
        data = options.get("data", {})
        actions = options.get("actions", [])
        timeout = options.get("timeout")
        default = options.get("default")
        config_key = options.get("config_key")

        # Build metadata with custom component info
        metadata = {
            "component_type": component_type,
            "data": data,
            "actions": actions,
        }

        logger.info(f"Human custom component requested: {component_type}")

        # CRITICAL: Wrap HITL call in checkpoint for transparent durability
        def checkpoint_fn():
            return self.execution_context.wait_for_human(
                request_type="custom",
                message=message,
                timeout_seconds=timeout,
                default_value=default,
                options=None,
                metadata=metadata,
                config_key=config_key,
            )

        response = self.execution_context.checkpoint(checkpoint_fn, "hitl_custom")

        return response.value

    def __repr__(self) -> str:
        return f"HumanPrimitive(config_keys={list(self.hitl_config.keys())})"
