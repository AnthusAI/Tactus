"""
Tactus IDE Backend Server

Provides LSP (Language Server Protocol) support and SSE for the Tactus IDE.
This backend runs locally (development) or as a service (production).
"""
import os
import json
import logging
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from lsp_server import LSPServer

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)
# Let Flask-SocketIO auto-detect the best async mode
socketio = SocketIO(app, cors_allowed_origins="*", logger=False, engineio_logger=False)

# Initialize LSP server
lsp_server = LSPServer()

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "service": "tactus-ide-backend"})

@app.route('/api/file', methods=['GET', 'POST'])
def file_operations():
    """
    Handle file operations (read/write .tactus.lua files).
    
    GET: Read file content
    POST: Write file content
    """
    if request.method == 'GET':
        file_path = request.args.get('path')
        if not file_path:
            return jsonify({"error": "Missing 'path' parameter"}), 400
        
        try:
            path = Path(file_path)
            if not path.exists():
                return jsonify({"error": f"File not found: {file_path}"}), 404
            
            content = path.read_text()
            return jsonify({
                "path": str(path),
                "content": content,
                "name": path.name
            })
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return jsonify({"error": str(e)}), 500
    
    elif request.method == 'POST':
        data = request.json
        file_path = data.get('path')
        content = data.get('content')
        
        if not file_path or content is None:
            return jsonify({"error": "Missing 'path' or 'content'"}), 400
        
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            return jsonify({
                "success": True,
                "path": str(path)
            })
        except Exception as e:
            logger.error(f"Error writing file {file_path}: {e}")
            return jsonify({"error": str(e)}), 500

@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection."""
    logger.info('Client connected')
    emit('connected', {'status': 'ok'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection."""
    logger.info('Client disconnected')

@socketio.on('lsp')
def handle_lsp_message(message):
    """
    Handle LSP JSON-RPC messages via WebSocket.
    
    LSP protocol uses JSON-RPC 2.0 format:
    {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "textDocument/didChange",
        "params": {...}
    }
    """
    try:
        logger.debug(f"Received LSP message: {message.get('method')}")
        response = lsp_server.handle_message(message)
        
        if response:
            emit('lsp', response)
    except Exception as e:
        logger.error(f"Error handling LSP message: {e}")
        error_response = {
            "jsonrpc": "2.0",
            "id": message.get('id'),
            "error": {
                "code": -32603,
                "message": str(e)
            }
        }
        emit('lsp', error_response)

@socketio.on('lsp_notification')
def handle_lsp_notification(message):
    """Handle LSP notifications (no response expected)."""
    try:
        logger.debug(f"Received LSP notification: {message.get('method')}")
        lsp_server.handle_notification(message)
    except Exception as e:
        logger.error(f"Error handling LSP notification: {e}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))  # Changed from 5000 to 5001 (macOS AirPlay uses 5000)
    logger.info(f"Starting Tactus IDE Backend on port {port}")
    # Use socketio.run which handles WebSocket properly
    socketio.run(app, host='127.0.0.1', port=port, debug=False, use_reloader=False, log_output=False, allow_unsafe_werkzeug=True)


