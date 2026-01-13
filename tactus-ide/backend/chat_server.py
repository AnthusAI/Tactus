"""
Flask routes for AI coding assistant chat API.

Provides REST and WebSocket endpoints for chat functionality.
"""

import asyncio
import logging
import uuid
from flask import Blueprint, request, jsonify
import json

from assistant_service import AssistantService

logger = logging.getLogger(__name__)

# Create blueprint
chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")

# Active conversations
conversations = {}


def get_or_create_service(workspace_root: str, config: dict) -> AssistantService:
    """Get or create assistant service for workspace."""
    # For now, create a new service each time
    # TODO: Cache services per workspace
    return AssistantService(workspace_root, config)


@chat_bp.route("/test", methods=["GET"])
def test_endpoint():
    """Test endpoint to verify chat routes are registered."""
    return jsonify({"status": "ok", "message": "Chat routes are working"})


@chat_bp.route("/start", methods=["POST"])
def start_conversation():
    """
    Start a new conversation.

    Request body:
        {
            "workspace_root": "/path/to/workspace",
            "config": {
                "provider": "openai",
                "model": "gpt-4o",
                ...
            }
        }

    Response:
        {
            "conversation_id": "uuid",
            "status": "active"
        }
    """
    try:
        data = request.get_json()
        workspace_root = data.get("workspace_root")
        config = data.get("config", {})

        if not workspace_root:
            return jsonify({"error": "workspace_root required"}), 400

        # Generate conversation ID
        conversation_id = str(uuid.uuid4())

        # Create service
        service = get_or_create_service(workspace_root, config)

        # Start conversation (async)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(service.start_conversation(conversation_id))
        loop.close()

        # Store service
        conversations[conversation_id] = service

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error starting conversation: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@chat_bp.route("/message", methods=["POST"])
def send_message():
    """
    Send a message to the assistant (non-streaming).

    Request body:
        {
            "conversation_id": "uuid",
            "message": "user message"
        }

    Response:
        {
            "events": [
                {"type": "message", "content": "...", "role": "assistant"},
                ...
            ]
        }
    """
    try:
        data = request.get_json()
        conversation_id = data.get("conversation_id")
        message = data.get("message")

        if not conversation_id or not message:
            return jsonify({"error": "conversation_id and message required"}), 400

        # Get service
        service = conversations.get(conversation_id)
        if not service:
            return jsonify({"error": "Conversation not found"}), 404

        # Send message and collect events
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        events = []

        async def collect_events():
            async for event in service.send_message(message):
                events.append(event)

        loop.run_until_complete(collect_events())
        loop.close()

        return jsonify({"events": events})

    except Exception as e:
        logger.error(f"Error sending message: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@chat_bp.route("/stream", methods=["POST"])
def stream_message():
    """
    Send a message and stream the response using Server-Sent Events.

    Request body:
        {
            "workspace_root": "/path/to/workspace",
            "message": "user message",
            "config": {
                "provider": "openai",
                "model": "gpt-4o",
                "temperature": 0.7,
                "max_tokens": 4000
            }
        }

    Returns:
        Server-Sent Events stream with assistant responses
    """
    from flask import Response, stream_with_context

    try:
        data = request.get_json()
        workspace_root = data.get("workspace_root")
        user_message = data.get("message")
        config = data.get("config", {})

        if not workspace_root or not user_message:
            return jsonify({"error": "workspace_root and message required"}), 400

        # Create or get service
        conversation_id = str(uuid.uuid4())
        service = get_or_create_service(workspace_root, config)

        def generate():
            """Generator function that yields SSE events."""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                # Start conversation (configures DSPy LM internally)
                loop.run_until_complete(service.start_conversation(conversation_id))

                # Send immediate thinking indicator
                yield f"data: {json.dumps({'type': 'thinking', 'content': 'Processing your request...'})}\n\n"

                # Create async generator
                async_gen = service.send_message(user_message)

                # Consume events one at a time and yield immediately
                while True:
                    try:
                        event = loop.run_until_complete(async_gen.__anext__())
                        yield f"data: {json.dumps(event)}\n\n"
                    except StopAsyncIteration:
                        break

            except Exception as e:
                logger.error(f"Error streaming message: {e}", exc_info=True)
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
            finally:
                loop.close()

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    except Exception as e:
        logger.error(f"Error in stream endpoint: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@chat_bp.route("/history/<conversation_id>", methods=["GET"])
def get_history(conversation_id: str):
    """
    Get conversation history.

    Response:
        {
            "conversation_id": "uuid",
            "history": [
                {"role": "user", "content": "..."},
                {"role": "assistant", "content": "..."},
                ...
            ]
        }
    """
    try:
        service = conversations.get(conversation_id)
        if not service:
            return jsonify({"error": "Conversation not found"}), 404

        # Get history
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        history = loop.run_until_complete(service.get_history(conversation_id))
        loop.close()

        return jsonify({"conversation_id": conversation_id, "history": history})

    except Exception as e:
        logger.error(f"Error getting history: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@chat_bp.route("/resume/<conversation_id>", methods=["POST"])
def resume_conversation(conversation_id: str):
    """
    Resume a conversation from checkpoint.

    Request body:
        {
            "workspace_root": "/path/to/workspace",
            "config": {...}
        }

    Response:
        {
            "conversation_id": "uuid",
            "status": "resumed",
            "history": [...]
        }
    """
    try:
        data = request.get_json()
        workspace_root = data.get("workspace_root")
        config = data.get("config", {})

        if not workspace_root:
            return jsonify({"error": "workspace_root required"}), 400

        # Create service
        service = get_or_create_service(workspace_root, config)

        # Resume conversation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(service.resume_conversation(conversation_id))
        loop.close()

        # Store service
        conversations[conversation_id] = service

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error resuming conversation: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@chat_bp.route("/<conversation_id>", methods=["DELETE"])
def clear_conversation(conversation_id: str):
    """
    Clear a conversation.

    Response:
        {
            "conversation_id": "uuid",
            "status": "cleared"
        }
    """
    try:
        service = conversations.get(conversation_id)
        if not service:
            return jsonify({"error": "Conversation not found"}), 404

        # Clear conversation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(service.clear_conversation(conversation_id))
        loop.close()

        # Remove from active conversations
        del conversations[conversation_id]

        return jsonify({"conversation_id": conversation_id, "status": "cleared"})

    except Exception as e:
        logger.error(f"Error clearing conversation: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


def register_chat_routes(app):
    """Register chat routes with Flask app."""
    try:
        # Register REST blueprint (includes SSE streaming endpoint)
        logger.info("Registering chat REST blueprint...")
        app.register_blueprint(chat_bp)
        logger.info("✓ Successfully registered chat routes (REST + SSE streaming)")

    except Exception as e:
        logger.error(f"✗ Failed to register chat routes: {e}", exc_info=True)
        raise
