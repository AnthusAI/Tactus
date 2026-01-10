"""
Coding Assistant Agent for Tactus IDE.

Provides an AI-powered coding assistant that uses Tactus primitives
to interact with the workspace, files, and user.
"""

import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
import dspy
from tactus.primitives.file import FilePrimitive
from tactus.primitives.human import HumanPrimitive
from tactus.core.execution_context import ExecutionContext

logger = logging.getLogger(__name__)


class CodingAssistantAgent:
    """
    AI Coding Assistant powered by Tactus primitives.

    Uses DSPy for agent inference and Tactus primitives for:
    - File operations (FilePrimitive with workspace sandboxing)
    - Human interaction (HumanPrimitive for HITL)
    - Tool tracking (ToolPrimitive)
    """

    def __init__(self, workspace_root: str, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the coding assistant.

        Args:
            workspace_root: Root directory for file operations (sandboxed)
            config: Optional configuration dict with provider/model settings
        """
        self.workspace_root = Path(workspace_root).resolve()
        self.config = config or {}

        # Initialize Tactus primitives
        self.file_primitive = FilePrimitive(base_path=str(self.workspace_root))

        # Create a minimal execution context for Human primitive
        # (We don't need full runtime features, just HITL support)
        self.execution_context = self._create_execution_context()
        self.human_primitive = HumanPrimitive(self.execution_context)

        # Chat history
        self.messages: List[Dict[str, Any]] = []

        # Initialize DSPy with configured model
        self._setup_dspy()

        logger.info(f"CodingAssistantAgent initialized with workspace: {self.workspace_root}")

    def _create_execution_context(self) -> ExecutionContext:
        """Create a minimal execution context for primitives."""
        # Import here to avoid circular dependencies
        from tactus.protocols.hitl import HITLResponse

        class MinimalExecutionContext:
            """Minimal context that supports wait_for_human."""

            def __init__(self):
                self._inside_checkpoint = False
                self.hitl_handler = None

            def wait_for_human(
                self,
                request_type: str,
                message: str,
                timeout_seconds: Optional[int] = None,
                default_value: Any = None,
                options: Optional[List[Dict[str, Any]]] = None,
                metadata: Optional[Dict[str, Any]] = None,
            ) -> HITLResponse:
                """
                Handle human interaction requests.

                For the IDE, we'll emit events that the frontend can respond to.
                This is a simplified version - full HITL will be implemented
                via the streaming API.
                """
                logger.info(f"HITL request: {request_type} - {message}")

                # For now, return default values
                # The streaming API will handle actual HITL interaction
                return HITLResponse(
                    request_type=request_type, value=default_value, metadata=metadata or {}
                )

        return MinimalExecutionContext()

    def _setup_dspy(self):
        """Configure DSPy with the appropriate model."""
        # Get configuration
        assistant_config = self.config.get("coding_assistant", {})
        provider = assistant_config.get(
            "provider", os.environ.get("TACTUS_DEFAULT_PROVIDER", "openai")
        )
        model = assistant_config.get("model", os.environ.get("TACTUS_DEFAULT_MODEL", "gpt-4"))

        logger.info(f"Setting up DSPy with provider={provider}, model={model}")

        # Configure DSPy LM based on provider
        if provider == "openai":
            api_key = self.config.get("openai_api_key") or os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OpenAI API key not found in config or environment")

            lm = dspy.OpenAI(model=model, api_key=api_key, max_tokens=4000)
        elif provider == "anthropic":
            api_key = self.config.get("anthropic_api_key") or os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("Anthropic API key not found in config or environment")

            lm = dspy.Claude(model=model, api_key=api_key, max_tokens=4000)
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        dspy.settings.configure(lm=lm)

        # Create the agent signature
        self.agent = self._create_agent()

    def _create_agent(self):
        """Create the DSPy agent with appropriate signature."""

        class CodingAssistantSignature(dspy.Signature):
            """AI Coding Assistant for Tactus IDE.

            You are a helpful coding assistant integrated into the Tactus IDE.
            You can help users with:
            - Reading and analyzing code files
            - Writing and editing files
            - Explaining code concepts
            - Debugging issues
            - Refactoring code

            You have access to tools for file operations within the workspace.
            Always be helpful, concise, and accurate.
            """

            chat_history = dspy.InputField(desc="Previous conversation messages")
            user_message = dspy.InputField(desc="User's current message")
            workspace_root = dspy.InputField(desc="Root directory of the workspace")

            response = dspy.OutputField(desc="Your response to the user")
            tool_calls = dspy.OutputField(desc="List of tool calls to make (if any)")

        return dspy.ChainOfThought(CodingAssistantSignature)

    def process_message(self, user_message: str) -> Dict[str, Any]:
        """
        Process a user message and generate a response.

        Args:
            user_message: The user's message

        Returns:
            Dict with 'response' and optional 'tool_calls'
        """
        logger.info(f"Processing message: {user_message[:100]}...")

        # Add user message to history
        self.messages.append({"role": "user", "content": user_message})

        # Format chat history for DSPy
        chat_history_str = self._format_chat_history()

        # Get response from agent
        try:
            result = self.agent(
                chat_history=chat_history_str,
                user_message=user_message,
                workspace_root=str(self.workspace_root),
            )

            response = result.response
            tool_calls = result.tool_calls if hasattr(result, "tool_calls") else []

            # Add assistant response to history
            self.messages.append({"role": "assistant", "content": response})

            logger.info(f"Generated response: {response[:100]}...")

            return {"response": response, "tool_calls": tool_calls}

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            error_response = f"I encountered an error: {str(e)}"

            self.messages.append({"role": "assistant", "content": error_response})

            return {"response": error_response, "tool_calls": []}

    def _format_chat_history(self) -> str:
        """Format chat history as a string for the agent."""
        if not self.messages:
            return "No previous messages."

        formatted = []
        for msg in self.messages[-10:]:  # Last 10 messages
            role = msg["role"].capitalize()
            content = msg["content"]
            formatted.append(f"{role}: {content}")

        return "\n".join(formatted)

    # Tool methods that can be called by the agent

    def read_file(self, path: str) -> str:
        """
        Read a file from the workspace.

        Args:
            path: Relative path to file within workspace

        Returns:
            File contents as string
        """
        try:
            logger.info(f"Tool call: read_file({path})")
            content = self.file_primitive.read(path)
            return content
        except Exception as e:
            logger.error(f"Error reading file {path}: {e}")
            return f"Error reading file: {str(e)}"

    def write_file(self, path: str, content: str) -> str:
        """
        Write content to a file in the workspace.

        Args:
            path: Relative path to file within workspace
            content: Content to write

        Returns:
            Success message or error
        """
        try:
            logger.info(f"Tool call: write_file({path}, {len(content)} bytes)")
            self.file_primitive.write(path, content)
            return f"Successfully wrote {len(content)} bytes to {path}"
        except Exception as e:
            logger.error(f"Error writing file {path}: {e}")
            return f"Error writing file: {str(e)}"

    def list_directory(self, path: str = ".") -> str:
        """
        List files in a directory within the workspace.

        Args:
            path: Relative path to directory within workspace

        Returns:
            Formatted list of files and directories
        """
        try:
            logger.info(f"Tool call: list_directory({path})")

            # Resolve path safely
            target_path = self.file_primitive._resolve_path(path)

            if not target_path.exists():
                return f"Directory not found: {path}"

            if not target_path.is_dir():
                return f"Not a directory: {path}"

            # List contents
            entries = []
            for item in sorted(target_path.iterdir(), key=lambda x: (not x.is_dir(), x.name)):
                if item.is_dir():
                    entries.append(f"📁 {item.name}/")
                else:
                    size = item.stat().st_size
                    entries.append(f"📄 {item.name} ({size} bytes)")

            if not entries:
                return f"Directory is empty: {path}"

            return "\n".join(entries)

        except Exception as e:
            logger.error(f"Error listing directory {path}: {e}")
            return f"Error listing directory: {str(e)}"

    def file_exists(self, path: str) -> bool:
        """
        Check if a file exists in the workspace.

        Args:
            path: Relative path to file within workspace

        Returns:
            True if file exists, False otherwise
        """
        try:
            logger.info(f"Tool call: file_exists({path})")
            return self.file_primitive.exists(path)
        except Exception as e:
            logger.error(f"Error checking file existence {path}: {e}")
            return False

    def reset_conversation(self):
        """Clear conversation history."""
        logger.info("Resetting conversation history")
        self.messages.clear()

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """
        Get list of available tools for the agent.

        Returns:
            List of tool definitions
        """
        return [
            {
                "name": "read_file",
                "description": "Read contents of a file in the workspace",
                "parameters": {"path": "Relative path to the file"},
            },
            {
                "name": "write_file",
                "description": "Write content to a file in the workspace",
                "parameters": {
                    "path": "Relative path to the file",
                    "content": "Content to write to the file",
                },
            },
            {
                "name": "list_directory",
                "description": "List files and directories in the workspace",
                "parameters": {"path": "Relative path to directory (default: current directory)"},
            },
            {
                "name": "file_exists",
                "description": "Check if a file exists in the workspace",
                "parameters": {"path": "Relative path to the file"},
            },
        ]
