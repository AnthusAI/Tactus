"""
Length-prefixed JSON protocol for broker communication.

This module provides utilities for sending and receiving JSON messages
with a length prefix, avoiding the buffer size limitations of newline-delimited JSON.

Wire format:
    <10-digit-decimal-length>\n<json-payload>

Example:
    0000000123
    {"id":"abc","method":"llm.chat","params":{...}}
"""

import json
import asyncio
import logging
from typing import Any, Dict, AsyncIterator

import anyio
from anyio.streams.buffered import BufferedByteReceiveStream

logger = logging.getLogger(__name__)

# Length prefix is exactly 10 decimal digits + newline
LENGTH_PREFIX_SIZE = 11  # "0000000123\n"
MAX_MESSAGE_SIZE = 100 * 1024 * 1024  # 100MB safety limit


async def write_message(writer: asyncio.StreamWriter, message: Dict[str, Any]) -> None:
    """
    Write a JSON message with length prefix.

    Args:
        writer: asyncio StreamWriter
        message: Dictionary to encode as JSON

    Raises:
        ValueError: If message is too large
    """
    json_bytes = json.dumps(message).encode("utf-8")
    length = len(json_bytes)

    if length > MAX_MESSAGE_SIZE:
        raise ValueError(f"Message size {length} exceeds maximum {MAX_MESSAGE_SIZE}")

    # Write 10-digit length prefix + newline
    length_prefix = f"{length:010d}\n".encode("ascii")
    writer.write(length_prefix)
    writer.write(json_bytes)
    await writer.drain()


async def read_message(reader: asyncio.StreamReader) -> Dict[str, Any]:
    """
    Read a JSON message with length prefix.

    Args:
        reader: asyncio StreamReader

    Returns:
        Parsed JSON message as dictionary

    Raises:
        EOFError: If connection closed
        ValueError: If message is invalid or too large
    """
    # Read exactly 11 bytes for length prefix
    length_bytes = await reader.readexactly(LENGTH_PREFIX_SIZE)

    if not length_bytes:
        raise EOFError("Connection closed")

    try:
        length_str = length_bytes[:10].decode("ascii")
        length = int(length_str)
    except (ValueError, UnicodeDecodeError) as e:
        raise ValueError(f"Invalid length prefix: {length_bytes!r}") from e

    if length > MAX_MESSAGE_SIZE:
        raise ValueError(f"Message size {length} exceeds maximum {MAX_MESSAGE_SIZE}")

    if length == 0:
        raise ValueError("Zero-length message not allowed")

    # Read exactly that many bytes for the JSON payload
    json_bytes = await reader.readexactly(length)

    try:
        message = json.loads(json_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ValueError("Invalid JSON payload") from e

    return message


async def read_messages(reader: asyncio.StreamReader) -> AsyncIterator[Dict[str, Any]]:
    """
    Read a stream of length-prefixed JSON messages.

    Args:
        reader: asyncio StreamReader

    Yields:
        Parsed JSON messages as dictionaries

    Stops when connection is closed or error occurs.
    """
    try:
        while True:
            message = await read_message(reader)
            yield message
    except EOFError:
        return
    except asyncio.IncompleteReadError:
        return


# AnyIO-compatible versions for broker server
async def write_message_anyio(stream: anyio.abc.ByteStream, message: Dict[str, Any]) -> None:
    """
    Write a JSON message with length prefix using AnyIO streams.

    Args:
        stream: anyio ByteStream
        message: Dictionary to encode as JSON

    Raises:
        ValueError: If message is too large
    """
    json_bytes = json.dumps(message).encode("utf-8")
    length = len(json_bytes)

    if length > MAX_MESSAGE_SIZE:
        raise ValueError(f"Message size {length} exceeds maximum {MAX_MESSAGE_SIZE}")

    # Write 10-digit length prefix + newline
    length_prefix = f"{length:010d}\n".encode("ascii")
    await stream.send(length_prefix)
    await stream.send(json_bytes)


async def read_message_anyio(stream: BufferedByteReceiveStream) -> Dict[str, Any]:
    """
    Read a JSON message with length prefix using AnyIO streams.

    Args:
        stream: anyio BufferedByteReceiveStream

    Returns:
        Parsed JSON message as dictionary

    Raises:
        EOFError: If connection closed
        ValueError: If message is invalid or too large
    """
    # Read exactly 11 bytes for length prefix
    length_bytes = await stream.receive_exactly(LENGTH_PREFIX_SIZE)

    if not length_bytes:
        raise EOFError("Connection closed")

    try:
        length_str = length_bytes[:10].decode("ascii")
        length = int(length_str)
    except (ValueError, UnicodeDecodeError) as e:
        raise ValueError(f"Invalid length prefix: {length_bytes!r}") from e

    if length > MAX_MESSAGE_SIZE:
        raise ValueError(f"Message size {length} exceeds maximum {MAX_MESSAGE_SIZE}")

    if length == 0:
        raise ValueError("Zero-length message not allowed")

    # Read exactly that many bytes for the JSON payload
    json_bytes = await stream.receive_exactly(length)

    try:
        message = json.loads(json_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ValueError("Invalid JSON payload") from e

    return message
