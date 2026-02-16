#!/usr/bin/env python3
"""
Stdio-based LSP server for VSCode extension.

Communicates via JSON-RPC over stdin/stdout using the pygls framework.
"""

import logging
import sys
from typing import Optional
from pygls.server import LanguageServer
from lsprotocol.types import (
    DidOpenTextDocumentParams,
    DidChangeTextDocumentParams,
    DidCloseTextDocumentParams,
    CompletionParams,
    CompletionList,
    HoverParams,
    SignatureHelpParams,
    SemanticTokensParams,
    SemanticTokens,
    TEXT_DOCUMENT_DID_OPEN,
    TEXT_DOCUMENT_DID_CHANGE,
    TEXT_DOCUMENT_DID_CLOSE,
    TEXT_DOCUMENT_COMPLETION,
    TEXT_DOCUMENT_HOVER,
    TEXT_DOCUMENT_SIGNATURE_HELP,
    TEXT_DOCUMENT_SEMANTIC_TOKENS_FULL,
)

from tactus_lsp_server.handler import TactusLSPHandler

# Configure logging to stderr (stdout is used for LSP communication)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# Create language server
server = LanguageServer("tactus-lsp-server", "v0.1.0")
handler = TactusLSPHandler()


@server.feature(TEXT_DOCUMENT_DID_OPEN)
async def did_open(ls: LanguageServer, params: DidOpenTextDocumentParams):
    """Handle document open notification."""
    uri = params.text_document.uri
    text = params.text_document.text

    logger.info(f"Document opened: {uri}")

    # Validate and send diagnostics
    diagnostics = handler.validate_document(uri, text)
    ls.publish_diagnostics(uri, diagnostics)


@server.feature(TEXT_DOCUMENT_DID_CHANGE)
async def did_change(ls: LanguageServer, params: DidChangeTextDocumentParams):
    """Handle document change notification."""
    uri = params.text_document.uri

    # Get full text from content changes
    # We use full document sync (change: 1) so contentChanges[0] has full text
    if params.content_changes:
        text = params.content_changes[0].text

        logger.debug(f"Document changed: {uri}")

        # Validate and send diagnostics
        diagnostics = handler.validate_document(uri, text)
        ls.publish_diagnostics(uri, diagnostics)


@server.feature(TEXT_DOCUMENT_DID_CLOSE)
async def did_close(ls: LanguageServer, params: DidCloseTextDocumentParams):
    """Handle document close notification."""
    uri = params.text_document.uri

    logger.info(f"Document closed: {uri}")
    handler.close_document(uri)


@server.feature(TEXT_DOCUMENT_COMPLETION)
async def completions(ls: LanguageServer, params: CompletionParams) -> CompletionList:
    """Handle completion request."""
    uri = params.text_document.uri
    position = {"line": params.position.line, "character": params.position.character}

    logger.debug(f"Completion requested at {uri}:{position}")

    items = handler.get_completions(uri, position)
    return CompletionList(is_incomplete=False, items=items)


@server.feature(TEXT_DOCUMENT_HOVER)
async def hover(ls: LanguageServer, params: HoverParams):
    """Handle hover request."""
    uri = params.text_document.uri
    position = {"line": params.position.line, "character": params.position.character}

    logger.debug(f"Hover requested at {uri}:{position}")

    return handler.get_hover(uri, position)


@server.feature(TEXT_DOCUMENT_SIGNATURE_HELP)
async def signature_help(ls: LanguageServer, params: SignatureHelpParams):
    """Handle signature help request."""
    uri = params.text_document.uri
    position = {"line": params.position.line, "character": params.position.character}

    logger.debug(f"Signature help requested at {uri}:{position}")

    return handler.get_signature_help(uri, position)


@server.feature(TEXT_DOCUMENT_SEMANTIC_TOKENS_FULL)
async def semantic_tokens_full(
    ls: LanguageServer, params: SemanticTokensParams
) -> Optional[SemanticTokens]:
    """Handle semantic tokens request."""
    uri = params.text_document.uri

    logger.debug(f"Semantic tokens requested for {uri}")

    result = handler.get_semantic_tokens(uri)
    if result and "data" in result:
        return SemanticTokens(data=result["data"])

    return None


def main():
    """Start the LSP server on stdio."""
    logger.info("Starting Tactus LSP Server...")
    try:
        server.start_io()
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
