# LLM Response Streaming

The Tactus IDE supports real-time streaming of LLM responses, allowing users to see text appear incrementally as the model generates it.

## How It Works

When running a procedure in the IDE, agent responses are streamed in real-time:

1. **Loading indicator** appears when agent turn starts
2. **Text streams in** word by word as the LLM generates it
3. **Final metrics** (cost, tokens, duration) appear when complete

## Limitations

### Streaming Only Works with Plain Text Responses

**Streaming is only available for agents without structured output validation.**

```lua
-- ✅ STREAMING WORKS - No outputs defined
main = procedure("main", {}, function()
    MyAgent.turn()
end)

-- ❌ STREAMING DISABLED - Has structured output
main = procedure("main", {
    output = {
        result = { type = "string", required = true }
    },
    state = {}
}, function()
    MyAgent.turn()
end)
```

### Why This Limitation Exists

Pydantic AI's `stream_text()` method only works with plain text responses. When using structured outputs (`output_type`), the library must:

1. Wait for the complete response
2. Parse it into the structured format
3. Validate it against the schema

This requires the full response before processing, making streaming impossible.

## Technical Details

### Backend Implementation

The streaming implementation is in `tactus/primitives/agent.py`:

- **Streaming mode**: Uses `agent.run_stream()` when `log_handler` exists and `result_type` is `None`
- **Regular mode**: Uses `agent.run()` for CLI or structured outputs
- **Events**: Emits `AgentStreamChunkEvent` for each text chunk

### Frontend Implementation

The IDE frontend handles streaming events:

- **Event type**: `AgentStreamChunkEvent` contains `chunk_text` and `accumulated_text`
- **Component**: `AgentStreamingComponent` displays the streaming text
- **Event filtering**: Only the latest chunk is shown (previous chunks are replaced)

### Event Flow

```
1. AgentTurnEvent(started) → Loading spinner
2. AgentStreamChunkEvent(chunk 1) → Show text (replace spinner)
3. AgentStreamChunkEvent(chunk 2) → Update text (replace chunk 1)
4. AgentStreamChunkEvent(chunk N) → Update text (replace chunk N-1)
5. CostEvent → Show final response with metrics (replace streaming)
```

## CLI vs IDE Behavior

- **CLI mode**: No streaming (uses regular `agent.run()`)
- **IDE mode**: Streaming enabled for plain text responses
- **Structured outputs**: No streaming in either mode

## Example

See `examples/streaming-test.tac` for a working example of streaming in action.

```lua
-- Streaming example
agent("storyteller", {
    provider = "openai",
    system_prompt = "You are a creative storyteller...",
    initial_message = "Tell me a short story",
    tools = {"done"},
})

main = procedure("main", {}, function()
    Storyteller.turn()  -- This will stream!
end)
```

## Future Improvements

Potential enhancements for streaming support:

1. **Partial structured output streaming**: Stream raw text while building structured output
2. **Token-by-token streaming**: Reduce chunk size for even smoother streaming
3. **Streaming with tool calls**: Show text and tool calls as they happen
4. **Configurable streaming**: Allow users to enable/disable streaming per agent

Note: These improvements would require changes to Pydantic AI's streaming API.
