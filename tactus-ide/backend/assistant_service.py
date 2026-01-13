"""
AI Coding Assistant Service using Tactus primitives.

Manages conversations with the coding assistant, using DSPy agents
to provide durable, HITL-enabled AI assistance.
"""

import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional, AsyncIterator

# Import DSPy for LM configuration
import dspy

# Import file tools
from assistant_tools import (
    search_files,
    FileToolsError,
    PathSecurityError,
)
from text_editor_tool import str_replace_based_edit_tool

logger = logging.getLogger(__name__)


class AssistantService:
    """
    Manages AI coding assistant using DSPy agents.

    Uses DSPyAgentHandle with:
    - SPECIFICATION.md in system prompt
    - File management tools (read, write, delete, move, copy, edit)
    - Streaming responses
    """

    def __init__(self, workspace_root: str, config: Dict[str, Any]):
        """
        Initialize assistant service.

        Args:
            workspace_root: Absolute path to workspace root
            config: Configuration dict with provider, model, etc.
        """
        self.workspace_root = workspace_root
        self.config = config
        self.agent: Optional[Any] = None  # dspy.ReAct agent
        self.lm: Optional[Any] = None  # dspy.LM instance
        self.conversation_id: Optional[str] = None
        self.websocket_manager: Optional[Any] = None
        self.message_history = []
        self.system_prompt: Optional[str] = None

    def set_websocket_manager(self, manager):
        """Set WebSocket manager for HITL communication."""
        self.websocket_manager = manager

    async def start_conversation(self, conversation_id: str) -> Dict[str, Any]:
        """
        Initialize DSPy agent for a conversation.

        Args:
            conversation_id: Unique conversation identifier

        Returns:
            Dict with conversation info
        """
        self.conversation_id = conversation_id

        # Configure DSPy LM
        provider = self.config.get("provider", "openai")
        model = self.config.get("model", "gpt-4o")
        temperature = self.config.get("temperature", 0.7)
        max_tokens = self.config.get("max_tokens", 4000)

        # Get API key from environment
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not set - agent may not work")

        # Normalize model name (handle both "gpt-4o" and "openai/gpt-4o" formats)
        if "/" in model:
            # Already has provider prefix
            model_name = model.split("/", 1)[1]
        else:
            model_name = model

        # Load SPECIFICATION.md
        spec_path = Path(__file__).parent.parent.parent / "SPECIFICATION.md"
        try:
            specification = spec_path.read_text()
        except Exception as e:
            logger.warning(f"Could not load SPECIFICATION.md: {e}")
            specification = "# Tactus Specification\n(Could not load specification)"

        system_prompt = f"""You are an AI coding assistant for the Tactus IDE.

You help users write, edit, and understand Tactus procedures (.tac files).

# Your Knowledge Base

{specification}

# Your Capabilities

You have access to these tools:
- read_file: Read any file in the workspace
- list_files: List files in a directory
- search_files: Search for files matching a pattern

Additional file operations (write, edit, delete, move, copy) are available but require user approval.

# Guidelines

1. Always read files before editing them
2. Be concise but thorough in explanations
3. Follow the Tactus specification exactly
4. Never use emojis - use Unicode symbols instead (✓ ✗ → • etc.)
5. When showing code examples, use proper markdown code blocks
6. If you're unsure, ask clarifying questions
7. Explain your reasoning clearly

# Current Workspace

Root: {self.workspace_root}

# Important

- All file paths are relative to the workspace root
- You can only access files within the workspace
- Be helpful and friendly, but professional
"""

        # Create tools as Python functions for dspy.ReAct
        def view_file_or_directory(command: str, path: str, view_range: list = None) -> str:
            """
            View file contents or list directory contents.

            Args:
                command: The command to execute (currently only 'view' is supported)
                path: Relative path to file or directory
                view_range: Optional [start_line, end_line] for viewing specific lines (1-indexed, use -1 for end)

            Returns:
                File contents with line numbers or directory listing
            """
            try:
                return str_replace_based_edit_tool(
                    workspace_root=self.workspace_root,
                    command=command,
                    path=path,
                    view_range=view_range,
                )
            except Exception as e:
                return f"Error: {str(e)}"

        def search_for_files(pattern: str) -> str:
            """
            Search for files matching a glob pattern.

            Args:
                pattern: Glob pattern to match files (e.g., '*.tac', 'examples/*.lua')

            Returns:
                List of matching file paths
            """
            try:
                files = search_files(self.workspace_root, pattern)
                if not files:
                    return f"No files found matching pattern: {pattern}"
                file_list = "\n".join(files)
                return f"Files matching '{pattern}':\n\n{file_list}"
            except (FileToolsError, PathSecurityError) as e:
                return f"Error searching files: {str(e)}"

        # Create DSPy LM without calling configure (to avoid async context issues)
        from tactus.dspy.config import create_lm

        model_for_litellm = f"{provider}/{model_name}" if provider else model_name

        # Create LM instance (doesn't call dspy.configure)
        self.lm = create_lm(model_for_litellm, temperature=temperature, max_tokens=max_tokens)

        # Wrap tools with dspy.Tool for native function calling support
        view_tool = dspy.Tool(view_file_or_directory)
        search_tool = dspy.Tool(search_for_files)

        # Create dspy.ReAct agent for automatic tool execution
        # ReAct handles the tool calling loop automatically across all LiteLLM providers
        # Agent will use the LM via dspy.context() when called
        self.agent = dspy.ReAct(
            signature="question -> answer",
            tools=[view_tool, search_tool],
            max_iters=10,  # Maximum tool execution iterations
        )

        # Store system prompt for use in send_message
        self.system_prompt = system_prompt

        logger.info(f"Started conversation {conversation_id} with {provider}/{model}")

        return {
            "conversation_id": conversation_id,
            "workspace_root": self.workspace_root,
            "status": "active",
        }

    async def send_message(self, message: str) -> AsyncIterator[Dict[str, Any]]:
        """
        Send user message to assistant, stream responses with ReAct tool execution.

        Args:
            message: User's message

        Yields:
            Event dicts:
            - {"type": "thinking", "content": "..."}
            - {"type": "message", "content": "...", "role": "assistant"} (incremental chunks)
            - {"type": "error", "error": "..."}
            - {"type": "done"}
        """
        if not self.agent:
            yield {"type": "error", "error": "Conversation not started"}
            return

        try:
            import threading
            import queue
            import re
            import dspy

            # Add user message to history
            self.message_history.append({"role": "user", "content": message})

            # Yield initial thinking indicator
            yield {"type": "thinking", "content": "Processing your request..."}

            # Build context with system prompt and history
            context = f"{self.system_prompt}\n\n"
            if len(self.message_history) > 1:
                context += "Previous conversation:\n"
                for msg in self.message_history[-10:]:  # Last 10 messages for context
                    role = msg["role"]
                    content = msg["content"]
                    context += f"{role}: {content}\n"
                context += "\n"
            context += f"User question: {message}"

            # Container for streaming chunks and completion
            chunk_queue = queue.Queue()
            result_container = {"result": None, "error": None}

            def run_streaming_agent():
                """Run ReAct agent with streaming support."""
                try:
                    # Create new event loop for this thread
                    import asyncio

                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    async def stream_chunks():
                        try:
                            # Use dspy.context to set LM for this async task
                            with dspy.context(lm=self.lm):
                                # Create StreamListener with allow_reuse=True for ReAct iterations
                                stream_listener = dspy.streaming.StreamListener(
                                    signature_field_name="answer", allow_reuse=True
                                )

                                # Create status message provider for tool call feedback
                                class ToolStatusProvider(dspy.streaming.StatusMessageProvider):
                                    def tool_start_status_message(self, instance, inputs):
                                        tool_name = getattr(instance, "name", "tool")
                                        # Format inputs nicely
                                        if inputs:
                                            # Unwrap kwargs if present
                                            actual_inputs = inputs
                                            if len(inputs) == 1 and "kwargs" in inputs:
                                                actual_inputs = inputs["kwargs"]

                                            # Convert inputs dict to readable format with wrapping
                                            params = []
                                            for key, value in actual_inputs.items():
                                                # Truncate long values
                                                str_value = str(value)
                                                if len(str_value) > 50:
                                                    str_value = str_value[:47] + "..."
                                                params.append(f"{key} = {str_value}")
                                            params_str = ", ".join(params)
                                            return f"{tool_name}  {params_str}"
                                        return tool_name

                                    def tool_end_status_message(self, outputs):
                                        return None  # Don't show end message

                                # Wrap agent with streamify
                                streaming_agent = dspy.streamify(
                                    self.agent,
                                    stream_listeners=[stream_listener],
                                    status_message_provider=ToolStatusProvider(),
                                )

                                # Call agent - returns async generator
                                async for chunk in streaming_agent(question=context):
                                    # Check if this is a status message (tool call)
                                    if isinstance(chunk, dspy.streaming.StatusMessage):
                                        chunk_queue.put(("status", chunk.message))
                                    # Check if this is a streaming token
                                    elif isinstance(chunk, dspy.streaming.StreamResponse):
                                        chunk_queue.put(("chunk", chunk.chunk))
                                    # Check if this is the final prediction
                                    elif isinstance(chunk, dspy.Prediction):
                                        result_container["result"] = chunk
                        except Exception as e:
                            logger.error(f"Streaming error: {e}", exc_info=True)
                            result_container["error"] = e
                        finally:
                            chunk_queue.put(("done", None))

                    loop.run_until_complete(stream_chunks())

                except Exception as e:
                    logger.error(f"Agent error: {e}", exc_info=True)
                    result_container["error"] = e
                    chunk_queue.put(("done", None))

            # Start agent in background thread
            agent_thread = threading.Thread(target=run_streaming_agent, daemon=True)
            agent_thread.start()

            # ReAct markup patterns to filter out (for non-streaming fallback)
            REACT_PATTERNS = [
                re.compile(r"^Thought:\s*", re.MULTILINE),
                re.compile(r"^Action:\s*", re.MULTILINE),
                re.compile(r"^Observation:\s*", re.MULTILINE),
            ]
            ANSWER_PATTERN = re.compile(r"^Answer:\s*", re.MULTILINE)

            accumulated_text = ""

            # Process streaming chunks - ReAct streams answer directly without markup
            while True:
                try:
                    msg_type, msg_data = chunk_queue.get(timeout=120.0)

                    if msg_type == "done":
                        break

                    if msg_type == "status" and msg_data:
                        # Tool call status message
                        yield {
                            "type": "status",
                            "content": msg_data,
                            "role": "assistant",
                        }

                    elif msg_type == "chunk" and msg_data:
                        # ReAct streams the answer field directly, no filtering needed
                        accumulated_text += msg_data
                        yield {
                            "type": "message",
                            "content": msg_data,
                            "role": "assistant",
                        }

                except queue.Empty:
                    logger.warning("Timeout waiting for streaming chunks")
                    break

            # Check for errors
            if result_container["error"]:
                raise result_container["error"]

            # Fallback: If no streaming chunks were sent, extract answer from result
            if not accumulated_text and result_container["result"]:
                result = result_container["result"]
                if hasattr(result, "answer"):
                    response_text = result.answer
                elif hasattr(result, "response"):
                    response_text = result.response
                elif isinstance(result, dict) and "answer" in result:
                    response_text = result["answer"]
                else:
                    response_text = str(result)

                # Filter out ReAct markup
                for pattern in REACT_PATTERNS:
                    response_text = pattern.sub("", response_text)
                response_text = ANSWER_PATTERN.sub("", response_text)

                if response_text.strip():
                    accumulated_text = response_text
                    yield {"type": "message", "content": response_text, "role": "assistant"}

            # Add assistant response to history
            if accumulated_text:
                self.message_history.append({"role": "assistant", "content": accumulated_text})

            yield {"type": "done"}

        except Exception as e:
            logger.error(f"Error in send_message: {e}", exc_info=True)
            yield {"type": "error", "error": str(e)}

    async def resume_conversation(self, conversation_id: str) -> Dict[str, Any]:
        """
        Resume a conversation from checkpoint.

        Args:
            conversation_id: ID of conversation to resume

        Returns:
            Dict with conversation info and history
        """
        logger.info(f"Resuming conversation {conversation_id}")

        return {
            "conversation_id": conversation_id,
            "status": "resumed",
            "history": self.message_history,
        }

    async def get_history(self, conversation_id: str) -> list:
        """
        Get conversation history.

        Args:
            conversation_id: ID of conversation

        Returns:
            List of message dicts
        """
        return self.message_history

    async def clear_conversation(self, conversation_id: str):
        """
        Clear conversation history.

        Args:
            conversation_id: ID of conversation to clear
        """
        logger.info(f"Clearing conversation {conversation_id}")
        self.message_history = []
