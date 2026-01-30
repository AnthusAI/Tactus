import asyncio

import anyio
import pytest
from anyio.streams.buffered import BufferedByteReceiveStream

from tactus.broker import protocol as broker_protocol
from tactus.broker.protocol import (
    read_message,
    read_messages,
    read_message_anyio,
    write_message,
    write_message_anyio,
)


class DummyWriter:
    def __init__(self):
        self.buffer = bytearray()

    def write(self, data: bytes) -> None:
        self.buffer.extend(data)

    async def drain(self) -> None:
        return None


class DummyByteStream:
    def __init__(self):
        self.buffer = bytearray()
        self.read_index = 0

    async def send(self, data: bytes) -> None:
        self.buffer.extend(data)

    async def receive(self) -> bytes:
        if self.read_index >= len(self.buffer):
            raise anyio.EndOfStream
        chunk = self.buffer[self.read_index :]
        self.read_index += len(chunk)
        return bytes(chunk)


class EmptyLengthReader:
    async def readexactly(self, _size: int) -> bytes:
        return b""


class IncompleteReader:
    async def readexactly(self, _size: int) -> bytes:
        raise asyncio.IncompleteReadError(partial=b"", expected=_size)


class EmptyLengthAnyioStream:
    async def receive_exactly(self, _size: int) -> bytes:
        return b""


@pytest.mark.asyncio
async def test_write_message_and_read_message_round_trip():
    writer = DummyWriter()
    payload = {"id": "1", "method": "ping"}

    await write_message(writer, payload)

    reader = asyncio.StreamReader()
    reader.feed_data(writer.buffer)
    reader.feed_eof()

    parsed = await read_message(reader)
    assert parsed == payload


@pytest.mark.asyncio
async def test_read_message_rejects_invalid_prefix():
    reader = asyncio.StreamReader()
    reader.feed_data(b"not-a-prefix")
    reader.feed_eof()

    with pytest.raises(ValueError):
        await read_message(reader)


@pytest.mark.asyncio
async def test_read_message_empty_length_raises_eof():
    reader = EmptyLengthReader()

    with pytest.raises(EOFError):
        await read_message(reader)


@pytest.mark.asyncio
async def test_read_message_rejects_zero_length_payload():
    reader = asyncio.StreamReader()
    reader.feed_data(b"0000000000\n")
    reader.feed_eof()

    with pytest.raises(ValueError):
        await read_message(reader)


@pytest.mark.asyncio
async def test_read_messages_iterates_multiple_payloads():
    writer = DummyWriter()
    await write_message(writer, {"id": "1"})
    await write_message(writer, {"id": "2"})

    reader = asyncio.StreamReader()
    reader.feed_data(writer.buffer)
    reader.feed_eof()

    results = []
    async for message in read_messages(reader):
        results.append(message["id"])

    assert results == ["1", "2"]


@pytest.mark.asyncio
async def test_read_messages_handles_incomplete_read():
    reader = IncompleteReader()
    results = []

    async for message in read_messages(reader):
        results.append(message)

    assert results == []


@pytest.mark.asyncio
async def test_read_messages_handles_eof_error():
    reader = EmptyLengthReader()
    results = []

    async for message in read_messages(reader):
        results.append(message)

    assert results == []


@pytest.mark.asyncio
async def test_read_messages_handles_incomplete_payload():
    writer = DummyWriter()
    payload = b"{}"
    writer.write(f"{len(payload) + 2:010d}\n".encode("ascii"))
    writer.write(payload)

    reader = asyncio.StreamReader()
    reader.feed_data(writer.buffer)
    reader.feed_eof()

    results = []
    async for message in read_messages(reader):
        results.append(message)

    assert results == []


@pytest.mark.asyncio
async def test_read_messages_handles_incomplete_read_error(monkeypatch):
    async def fake_read_message(_reader):
        raise asyncio.IncompleteReadError(partial=b"", expected=1)

    monkeypatch.setattr(broker_protocol, "read_message", fake_read_message)

    results = []
    async for message in read_messages(object()):
        results.append(message)

    assert results == []


@pytest.mark.asyncio
async def test_read_messages_handles_incomplete_stream_payload():
    reader = asyncio.StreamReader()
    reader.feed_data(b"0000000005\n{}")
    reader.feed_eof()

    results = []
    async for message in read_messages(reader):
        results.append(message)

    assert results == []


@pytest.mark.asyncio
async def test_anyio_write_and_read_message():
    stream = DummyByteStream()
    payload = {"id": "abc", "method": "test"}

    await write_message_anyio(stream, payload)

    buffered = BufferedByteReceiveStream(stream)
    parsed = await read_message_anyio(buffered)

    assert parsed == payload


@pytest.mark.asyncio
async def test_write_message_rejects_too_large(monkeypatch):
    writer = DummyWriter()
    monkeypatch.setattr(broker_protocol, "MAX_MESSAGE_SIZE", 1)

    with pytest.raises(ValueError):
        await write_message(writer, {"payload": "too big"})


@pytest.mark.asyncio
async def test_read_message_rejects_invalid_json_payload():
    reader = asyncio.StreamReader()
    payload = b"{"
    reader.feed_data(f"{len(payload):010d}\n".encode("ascii") + payload)
    reader.feed_eof()

    with pytest.raises(ValueError):
        await read_message(reader)


@pytest.mark.asyncio
async def test_read_message_rejects_too_large(monkeypatch):
    reader = asyncio.StreamReader()
    monkeypatch.setattr(broker_protocol, "MAX_MESSAGE_SIZE", 1)
    reader.feed_data(b"0000000002\n{}")
    reader.feed_eof()

    with pytest.raises(ValueError):
        await read_message(reader)


@pytest.mark.asyncio
async def test_read_messages_stops_on_eof():
    reader = asyncio.StreamReader()
    reader.feed_eof()

    results = []
    async for message in read_messages(reader):
        results.append(message)

    assert results == []


@pytest.mark.asyncio
async def test_anyio_read_rejects_invalid_prefix():
    stream = DummyByteStream()
    stream.buffer.extend(b"abcdefghij\n")

    buffered = BufferedByteReceiveStream(stream)
    with pytest.raises(ValueError):
        await read_message_anyio(buffered)


@pytest.mark.asyncio
async def test_anyio_read_empty_length_raises_eof():
    buffered = EmptyLengthAnyioStream()

    with pytest.raises(EOFError):
        await read_message_anyio(buffered)


@pytest.mark.asyncio
async def test_anyio_read_rejects_zero_length():
    stream = DummyByteStream()
    stream.buffer.extend(b"0000000000\n")

    buffered = BufferedByteReceiveStream(stream)
    with pytest.raises(ValueError):
        await read_message_anyio(buffered)


@pytest.mark.asyncio
async def test_anyio_read_rejects_too_large(monkeypatch):
    stream = DummyByteStream()
    monkeypatch.setattr(broker_protocol, "MAX_MESSAGE_SIZE", 1)
    stream.buffer.extend(b"0000000002\n{}")

    buffered = BufferedByteReceiveStream(stream)
    with pytest.raises(ValueError):
        await read_message_anyio(buffered)


@pytest.mark.asyncio
async def test_anyio_read_rejects_invalid_json():
    stream = DummyByteStream()
    stream.buffer.extend(b"0000000001\n{")

    buffered = BufferedByteReceiveStream(stream)
    with pytest.raises(ValueError):
        await read_message_anyio(buffered)


@pytest.mark.asyncio
async def test_anyio_write_message_rejects_too_large(monkeypatch):
    stream = DummyByteStream()
    monkeypatch.setattr(broker_protocol, "MAX_MESSAGE_SIZE", 1)

    with pytest.raises(ValueError):
        await write_message_anyio(stream, {"payload": "too big"})
