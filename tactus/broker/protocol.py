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

import asyncio
import logging
import json
from typing import Any, AsyncIterator

import anyio
from anyio.streams.buffered import BufferedByteReceiveStream

logger = logging.getLogger(__name__)

# Length prefix is exactly 10 decimal digits + newline
LENGTH_PREFIX_SIZE = 11  # "0000000123\n"
MAX_MESSAGE_SIZE = 100 * 1024 * 1024  # 100MB safety limit


def _parse_length_prefix(length_prefix_bytes: bytes) -> int:
    try:
        length_text = length_prefix_bytes[:10].decode("ascii")
        payload_length = int(length_text)
    except (ValueError, UnicodeDecodeError) as error:
        raise ValueError(f"Invalid length prefix: {length_prefix_bytes!r}") from error

    if payload_length > MAX_MESSAGE_SIZE:
        raise ValueError(f"Message size {payload_length} exceeds maximum {MAX_MESSAGE_SIZE}")

    if payload_length == 0:
        raise ValueError("Zero-length message not allowed")

    return payload_length


def _serialize_json_payload(message: dict[str, Any]) -> bytes:
    json_payload_bytes = json.dumps(message).encode("utf-8")
    payload_length = len(json_payload_bytes)

    if payload_length > MAX_MESSAGE_SIZE:
        raise ValueError(f"Message size {payload_length} exceeds maximum {MAX_MESSAGE_SIZE}")

    return json_payload_bytes


async def write_message(writer: asyncio.StreamWriter, message: dict[str, Any]) -> None:
    """
    Write a JSON message with length prefix.

    Args:
        writer: asyncio StreamWriter
        message: Dictionary to encode as JSON

    Raises:
        ValueError: If message is too large
    """
    json_payload_bytes = _serialize_json_payload(message)
    payload_length = len(json_payload_bytes)

    # Write 10-digit length prefix + newline
    length_prefix = f"{payload_length:010d}\n".encode("ascii")
    writer.write(length_prefix)
    writer.write(json_payload_bytes)
    await writer.drain()


async def read_message(reader: asyncio.StreamReader) -> dict[str, Any]:
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
    length_prefix_bytes = await reader.readexactly(LENGTH_PREFIX_SIZE)

    if not length_prefix_bytes:
        raise EOFError("Connection closed")

    payload_length = _parse_length_prefix(length_prefix_bytes)

    # Read exactly that many bytes for the JSON payload
    json_payload_bytes = await reader.readexactly(payload_length)

    try:
        message = json.loads(json_payload_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError("Invalid JSON payload") from error

    return message


async def read_messages(reader: asyncio.StreamReader) -> AsyncIterator[dict[str, Any]]:
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
    except asyncio.IncompleteReadError:
        return
    except EOFError:
        return


# AnyIO-compatible versions for broker server
async def write_message_anyio(stream: anyio.abc.ByteStream, message: dict[str, Any]) -> None:
    """
    Write a JSON message with length prefix using AnyIO streams.

    Args:
        stream: anyio ByteStream
        message: Dictionary to encode as JSON

    Raises:
        ValueError: If message is too large
    """
    json_payload_bytes = _serialize_json_payload(message)
    payload_length = len(json_payload_bytes)

    # Write 10-digit length prefix + newline
    length_prefix = f"{payload_length:010d}\n".encode("ascii")
    await stream.send(length_prefix)
    await stream.send(json_payload_bytes)


async def read_message_anyio(stream: BufferedByteReceiveStream) -> dict[str, Any]:
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
    length_prefix_bytes = await stream.receive_exactly(LENGTH_PREFIX_SIZE)

    if not length_prefix_bytes:
        raise EOFError("Connection closed")

    payload_length = _parse_length_prefix(length_prefix_bytes)

    # Read exactly that many bytes for the JSON payload
    json_payload_bytes = await stream.receive_exactly(payload_length)

    try:
        message = json.loads(json_payload_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError("Invalid JSON payload") from error

    return message
