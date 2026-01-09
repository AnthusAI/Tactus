# LLM Response Streaming

The Tactus IDE supports real-time streaming of LLM responses, allowing users to see text appear incrementally as the model generates it.

## How It Works

When running a procedure in the IDE, agent responses are streamed in real-time:

1. **Loading indicator** appears when agent turn starts
2. **Text streams in** word by word as the LLM generates it
3. **Final metrics** (cost, tokens, duration) appear when complete

## Streaming with Output Validation

Streaming works alongside output validation. These are orthogonal concerns:

- **Streaming** = UI feature for real-time feedback during generation
- **Output validation** = Post-processing after response is complete

When you have an `output` block defined, the system will:
1. Stream raw text chunks to the UI as they're generated
2. After streaming completes, validate the full response against the schema

```lua
-- STREAMING WORKS - even with outputs defined
storyteller = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = "You are a creative storyteller...",
}

output {
    story = field.string{description = "The generated story"},
}

local result = storyteller({message = "Write a short story"})
return { story = result.response }
```

## Disabling Streaming

You can explicitly disable streaming for an agent:

```lua
agent("assistant", {
    system_prompt = "You are helpful",
    model = "openai/gpt-4o",
    disable_streaming = true,  -- Force non-streaming mode
})
```

## Technical Details

### Backend Implementation (DSPy)

The streaming implementation is in `tactus/dspy/agent.py`:

- **Streaming detection**: The `_should_stream()` method checks if streaming should be enabled:
  - `log_handler` must be available (IDE mode)
  - `disable_streaming` must be false
- **Streaming mode**: Uses DSPy's native `dspy.settings.send_stream` with anyio memory streams
- **Events**: Emits `AgentStreamChunkEvent` for each text chunk

#### How DSPy Streaming Works

1. Create an `anyio.create_memory_object_stream()` pair
2. Set `dspy.settings.send_stream` to the send stream
3. Run the DSPy module call concurrently with chunk consumption
4. DSPy internally passes `stream=True` to LiteLLM
5. LiteLLM sends chunks through the stream
6. Each chunk triggers an `AgentStreamChunkEvent`

### Frontend Implementation

The IDE frontend handles streaming events:

- **Event type**: `AgentStreamChunkEvent` contains `chunk_text` and `accumulated_text`
- **Component**: `AgentStreamingComponent` displays the streaming text
- **Event filtering**: Only the latest chunk is shown (previous chunks are replaced)

Key files:
- `tactus-ide/frontend/src/hooks/useEventStream.ts` - SSE event handling
- `tactus-ide/frontend/src/components/events/AgentStreamingComponent.tsx` - Streaming UI
- `tactus-ide/frontend/src/components/events/EventRenderer.tsx` - Event routing

### Event Flow

```
1. AgentTurnEvent(started) -> Loading spinner
2. AgentStreamChunkEvent(chunk 1) -> Show text (replace spinner)
3. AgentStreamChunkEvent(chunk 2) -> Update text (replace chunk 1)
4. AgentStreamChunkEvent(chunk N) -> Update text (replace chunk N-1)
5. CostEvent -> Show final response with metrics (replace streaming)
```

## CLI vs IDE Behavior

- **CLI mode**: No streaming (no log_handler)
- **IDE mode**: Streaming enabled (works with or without output validation)

## Example

```lua
-- Streaming example
storyteller = Agent {
    provider = "openai",
    model = "gpt-4o",
    system_prompt = "You are a creative storyteller...",
}

local result = storyteller({message = "Tell me a short story"})  -- This will stream!
return { story = result.response }
```

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `disable_streaming` | boolean | false | Force non-streaming mode for this agent |

## Troubleshooting

### Streaming Not Working

1. **Check log_handler**: Streaming only works in IDE mode where `log_handler` is present
2. **Check disable_streaming**: May be explicitly disabled in agent config

### Chunks Not Appearing

1. **Check frontend connection**: Verify SSE connection is established
2. **Check event types**: Look for `agent_stream_chunk` events in browser console
3. **Check accumulated_text**: Each chunk should have growing `accumulated_text`

## Future Improvements

Potential enhancements for streaming support:

1. **Token-by-token streaming**: Reduce chunk size for even smoother streaming
2. **Streaming with tool calls**: Show text and tool calls as they happen
3. **CLI streaming**: Add streaming support to CLI mode with terminal output
