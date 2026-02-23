# Deepgram Utilities

The `tactus.deepgram` module provides helpers for working with Deepgram JSON transcripts. It can flatten transcripts into text, expose structured segments, and extract quotes with timestamps.

## Loading

```lua
local deepgram = require("tactus.deepgram")
```

## Text helpers

```lua
local text = deepgram.text(data, {source = "auto"})
local words = deepgram.words_text(data)
local sentences = deepgram.sentences_text(data)
local paragraphs = deepgram.paragraphs_text(data)
local utterances = deepgram.utterances_text(data)
```

Options:
- `include_speakers` (default true): Prefix segments with `Speaker N: ` when available.
- `separator`: Join segments with a custom separator.
- `source`: `"auto" | "utterances" | "sentences" | "paragraphs" | "words"`.
- `channel_mode` (default `"merge"`): Merge multi-channel words by time.
- `channel_index`: Select a channel (0-based) when not merging.
- `punctuated` (default true): Prefer `punctuated_word` for word text.

## Segments

```lua
local segments = deepgram.segments(data, {source = "utterances"})
for _, segment in ipairs(segments) do
    print(segment.text, segment.start, segment["end"], segment.speaker)
end
```

Each segment has:
- `text`, `start`, `end`
- `speaker`, `channel`
- `words` (word-level timing details)

## Quote extraction

```lua
local quote = deepgram.quote(data, {
    quote = "General Kenobi",
    method = "fuzzy",
    threshold = 0.8,
    window_slop = 2,
})

local llm_quote = deepgram.quote(data, {
    quote = "Hello world",
    method = "llm",
    client = {provider = "openai", model = "gpt-4o-mini"},
})
```

The quote result returns:
- `text`, `start`, `end`
- `speaker`, `channel`
- `confidence`, `method`

The LLM flow uses `biblicus.text.extract` with span markup and then aligns the span text back to timestamps.

## Notes

- Utterances and paragraphs only exist if Deepgram features were enabled when creating the transcript.
- When those features are missing, `source = "auto"` falls back to sentences (if present) and then words.
