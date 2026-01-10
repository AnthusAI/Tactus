"""
AI Coding Assistant Service using Tactus primitives.

Manages conversations with the coding assistant, using DSPy agents
to provide durable, HITL-enabled AI assistance.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional, AsyncIterator
import json

# Import DSPy for LM configuration
import dspy

# Import Tactus DSPy agent
from tactus.dspy.agent import DSPyAgentHandle

# Import IDELogHandler for streaming
from tactus.adapters.ide_log import IDELogHandler

# Import file tools
from assistant_tools import (
    read_file, list_files, search_files, write_file, edit_file,
    delete_file, move_file, copy_file, FileToolsError, PathSecurityError
)

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
        self.agent: Optional[DSPyAgentHandle] = None
        self.conversation_id: Optional[str] = None
        self.websocket_manager: Optional[Any] = None
        self.message_history = []
        self.log_handler: Optional[IDELogHandler] = None
        
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
        
        # Create tools as Python functions that the agent can call
        def read_file_tool(path: str) -> str:
            """Read a file from the workspace."""
            try:
                content = read_file(self.workspace_root, path)
                return f"File contents of {path}:\n\n{content}"
            except (FileToolsError, PathSecurityError) as e:
                return f"Error reading file: {str(e)}"
        
        def list_files_tool(path: str = ".") -> str:
            """List files in a directory."""
            try:
                files = list_files(self.workspace_root, path)
                file_list = "\n".join(
                    f"{'[DIR]' if f['type'] == 'directory' else '[FILE]'} {f['name']}"
                    for f in files
                )
                return f"Files in {path}:\n\n{file_list}"
            except (FileToolsError, PathSecurityError) as e:
                return f"Error listing files: {str(e)}"
        
        def search_files_tool(pattern: str) -> str:
            """Search for files matching a pattern."""
            try:
                files = search_files(self.workspace_root, pattern)
                if not files:
                    return f"No files found matching pattern: {pattern}"
                file_list = "\n".join(files)
                return f"Files matching '{pattern}':\n\n{file_list}"
            except (FileToolsError, PathSecurityError) as e:
                return f"Error searching files: {str(e)}"
        
        # Configure DSPy LM once at conversation start to avoid async context issues
        import dspy
        from tactus.dspy.config import configure_lm
        
        model_for_litellm = f"{provider}/{model_name}" if provider else model_name
        configure_lm(model_for_litellm, temperature=temperature, max_tokens=max_tokens)
        
        # Create log handler for streaming events
        self.log_handler = IDELogHandler()
        
        # Create DSPy agent with tools
        # Pass model in LiteLLM format (provider/model-name)
        self.agent = DSPyAgentHandle(
            name="coding_assistant",
            system_prompt=system_prompt,
            model=model_for_litellm,
            tools=[read_file_tool, list_files_tool, search_files_tool],
            temperature=temperature,
            max_tokens=max_tokens,
            log_handler=self.log_handler,
        )
        
        logger.info(f"Started conversation {conversation_id} with {provider}/{model}")
        
        return {
            "conversation_id": conversation_id,
            "workspace_root": self.workspace_root,
            "status": "active"
        }
        
    async def send_message(self, message: str) -> AsyncIterator[Dict[str, Any]]:
        """
        Send user message to assistant, stream responses.
        
        Args:
            message: User's message
            
        Yields:
            Event dicts:
            - {"type": "thinking", "content": "..."}
            - {"type": "message", "content": "...", "role": "assistant"} (incremental chunks)
            - {"type": "tool_call", "tool": "read_file", "args": {...}}
            - {"type": "tool_result", "tool": "read_file", "result": {...}}
            - {"type": "error", "error": "..."}
            - {"type": "done"}
        """
        if not self.agent:
            yield {"type": "error", "error": "Conversation not started"}
            return
            
        try:
            import threading
            import time
            from tactus.protocols.models import AgentStreamChunkEvent, AgentTurnEvent
            
            # Add user message to history
            self.message_history.append({"role": "user", "content": message})
            
            # Yield initial thinking indicator
            yield {"type": "thinking", "content": "Processing your request..."}
            
            # Container for agent result and completion status
            result_container = {"result": None, "error": None, "done": False}
            
            def run_agent():
                """Run agent in background thread."""
                try:
                    result = self.agent({"message": message})
                    result_container["result"] = result
                except Exception as e:
                    logger.error(f"Agent error: {e}", exc_info=True)
                    result_container["error"] = e
                finally:
                    result_container["done"] = True
            
            # Start agent in background thread
            agent_thread = threading.Thread(target=run_agent, daemon=True)
            agent_thread.start()
            
            # Poll for streaming events from log_handler
            accumulated_text = ""
            turn_started = False
            
            while not result_container["done"]:
                # Get events from log handler
                events = self.log_handler.get_events(timeout=0.1)
                
                for event in events:
                    if isinstance(event, AgentTurnEvent):
                        if event.stage == "started":
                            turn_started = True
                            logger.info(f"Agent turn started: {event.agent_name}")
                        elif event.stage == "completed":
                            logger.info(f"Agent turn completed: {event.agent_name}")
                    
                    elif isinstance(event, AgentStreamChunkEvent):
                        # Stream chunk to frontend
                        chunk_text = event.chunk_text
                        accumulated_text = event.accumulated_text
                        
                        logger.info(f"Streaming chunk: len={len(chunk_text)}, total={len(accumulated_text)}")
                        
                        yield {
                            "type": "message",
                            "content": chunk_text,
                            "role": "assistant"
                        }
                
                # Small sleep to avoid busy-waiting
                await asyncio.sleep(0.05)
            
            # Get any remaining events after agent completes
            events = self.log_handler.get_events(timeout=0.1)
            for event in events:
                if isinstance(event, AgentStreamChunkEvent):
                    chunk_text = event.chunk_text
                    accumulated_text = event.accumulated_text
                    
                    yield {
                        "type": "message",
                        "content": chunk_text,
                        "role": "assistant"
                    }
            
            # Check for errors
            if result_container["error"]:
                raise result_container["error"]
            
            # Extract final response text
            result = result_container["result"]
            if isinstance(result, dict) and "response" in result:
                response_text = result["response"]
            elif hasattr(result, "response"):
                response_text = result.response
            else:
                response_text = str(result)
            
            # If we didn't get any streaming chunks, yield the full response
            if not accumulated_text:
                logger.warning("No streaming chunks received, yielding full response")
                yield {
                    "type": "message",
                    "content": response_text,
                    "role": "assistant"
                }
                accumulated_text = response_text
            
            # Add assistant response to history
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
            "history": self.message_history
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