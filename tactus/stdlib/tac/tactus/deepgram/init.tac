-- Deepgram JSON utilities
--
-- Provides helpers for flattening Deepgram transcript JSON into text,
-- extracting segments, and locating quotes with timestamps.

local similarity = require("tactus.text.classify.similarity")
local biblicus = require("tactus.biblicus.text")

local function _get_opts(opts)
    if opts == nil then
        return {}
    end
    return opts
end

local function _word_text(word, opts)
    if word == nil then
        return ""
    end
    local punctuated = opts.punctuated
    if punctuated == nil then
        punctuated = true
    end
    if punctuated and word.punctuated_word then
        return word.punctuated_word
    end
    return word.word or word.punctuated_word or ""
end

local function _normalize_text(text)
    local value = string.lower(text or "")
    value = string.gsub(value, "[^%w%s]", " ")
    value = string.gsub(value, "%s+", " ")
    value = string.gsub(value, "^%s+", "")
    value = string.gsub(value, "%s+$", "")
    return value
end

local function _tokenize_words(text)
    local tokens = {}
    local normalized = _normalize_text(text)
    for token in string.gmatch(normalized, "%S+") do
        table.insert(tokens, token)
    end
    return tokens
end

local function _resolve_channel_index(opts)
    local idx = opts.channel_index
    if idx == nil then
        return 1
    end
    if idx < 0 then
        return 1
    end
    return idx + 1
end

local function _get_channel_mode(opts)
    return opts.channel_mode or "merge"
end

local function _get_channel_alternatives(data, opts)
    local results = (data or {}).results or {}
    local channels = results.channels or {}
    local mode = _get_channel_mode(opts)
    local output = {}

    if mode == "merge" then
        for idx, channel in ipairs(channels) do
            local alternatives = channel.alternatives or {}
            table.insert(output, {
                channel = idx - 1,
                alternative = alternatives[1] or {},
            })
        end
    else
        local index = _resolve_channel_index(opts)
        local channel = channels[index]
        if channel then
            local alternatives = channel.alternatives or {}
            output = {
                {
                    channel = index - 1,
                    alternative = alternatives[1] or {},
                },
            }
        end
    end

    return output
end

local function _collect_words(data, opts)
    local items = {}
    local channels = _get_channel_alternatives(data, opts)

    for _, entry in ipairs(channels) do
        local alt = entry.alternative or {}
        local words = alt.words or {}
        for _, word in ipairs(words) do
            local text = _word_text(word, opts)
            local normalized = _normalize_text(text)
            table.insert(items, {
                text = text,
                normalized = normalized,
                start = word.start,
                ["end"] = word["end"],
                speaker = word.speaker,
                channel = entry.channel,
            })
        end
    end

    if _get_channel_mode(opts) == "merge" then
        table.sort(items, function(a, b)
            local a_start = a.start or 0
            local b_start = b.start or 0
            if a_start == b_start then
                return (a.channel or 0) < (b.channel or 0)
            end
            return a_start < b_start
        end)
    end

    return items
end

local function _words_in_range(words, start_time, end_time, channel)
    local output = {}
    for _, word in ipairs(words) do
        if channel ~= nil and word.channel ~= channel then
            -- skip
        else
            local w_start = word.start or 0
            if w_start >= (start_time or 0) and w_start <= (end_time or w_start) then
                table.insert(output, word)
            end
        end
    end
    return output
end

local function _select_speaker(words)
    local counts = {}
    local best_speaker = nil
    local best_count = 0

    for _, word in ipairs(words or {}) do
        local speaker = word.speaker
        if speaker ~= nil then
            counts[speaker] = (counts[speaker] or 0) + 1
            if counts[speaker] > best_count then
                best_count = counts[speaker]
                best_speaker = speaker
            end
        end
    end

    return best_speaker
end

local function _segments_from_utterances(data, opts)
    local results = (data or {}).results or {}
    local utterances = results.utterances or {}
    local segments = {}

    for _, utterance in ipairs(utterances) do
        local words = {}
        local utter_words = utterance.words or {}
        for _, word in ipairs(utter_words) do
            local text = _word_text(word, opts)
            table.insert(words, {
                text = text,
                normalized = _normalize_text(text),
                start = word.start,
                ["end"] = word["end"],
                speaker = word.speaker or utterance.speaker,
                channel = utterance.channel,
            })
        end
        table.insert(segments, {
            text = utterance.transcript or "",
            start = utterance.start,
            ["end"] = utterance["end"],
            speaker = utterance.speaker,
            channel = utterance.channel,
            words = words,
        })
    end

    return segments
end

local function _segments_from_sentences(data, opts, all_words)
    local segments = {}
    local channels = _get_channel_alternatives(data, opts)

    for _, entry in ipairs(channels) do
        local alt = entry.alternative or {}
        local paragraphs = (alt.paragraphs or {}).paragraphs or {}
        for _, paragraph in ipairs(paragraphs) do
            local sentences = paragraph.sentences or {}
            for _, sentence in ipairs(sentences) do
                local words = _words_in_range(all_words, sentence.start, sentence["end"], entry.channel)
                table.insert(segments, {
                    text = sentence.text or "",
                    start = sentence.start,
                    ["end"] = sentence["end"],
                    speaker = _select_speaker(words),
                    channel = entry.channel,
                    words = words,
                })
            end
        end
    end

    if _get_channel_mode(opts) == "merge" then
        table.sort(segments, function(a, b)
            local a_start = a.start or 0
            local b_start = b.start or 0
            if a_start == b_start then
                return (a.channel or 0) < (b.channel or 0)
            end
            return a_start < b_start
        end)
    end

    return segments
end

local function _segments_from_paragraphs(data, opts, all_words)
    local segments = {}
    local channels = _get_channel_alternatives(data, opts)

    for _, entry in ipairs(channels) do
        local alt = entry.alternative or {}
        local paragraphs = (alt.paragraphs or {}).paragraphs or {}
        for _, paragraph in ipairs(paragraphs) do
            local sentences = paragraph.sentences or {}
            local text_parts = {}
            local start_time = nil
            local end_time = nil
            for _, sentence in ipairs(sentences) do
                if start_time == nil then
                    start_time = sentence.start
                end
                end_time = sentence["end"] or end_time
                table.insert(text_parts, sentence.text or "")
            end
            local words = _words_in_range(all_words, start_time, end_time, entry.channel)
            table.insert(segments, {
                text = table.concat(text_parts, " "),
                start = start_time,
                ["end"] = end_time,
                speaker = _select_speaker(words),
                channel = entry.channel,
                words = words,
            })
        end
    end

    if _get_channel_mode(opts) == "merge" then
        table.sort(segments, function(a, b)
            local a_start = a.start or 0
            local b_start = b.start or 0
            if a_start == b_start then
                return (a.channel or 0) < (b.channel or 0)
            end
            return a_start < b_start
        end)
    end

    return segments
end

local function _segments_from_words(data, opts)
    local segments = {}
    local words = _collect_words(data, opts)
    for _, word in ipairs(words) do
        table.insert(segments, {
            text = word.text,
            start = word.start,
            ["end"] = word["end"],
            speaker = word.speaker,
            channel = word.channel,
            words = {word},
        })
    end
    return segments
end

local function _has_utterances(data)
    local results = (data or {}).results or {}
    return results.utterances ~= nil and #results.utterances > 0
end

local function _has_sentences(data)
    local channels = _get_channel_alternatives(data, {})
    for _, entry in ipairs(channels) do
        local alt = entry.alternative or {}
        local paragraphs = (alt.paragraphs or {}).paragraphs or {}
        for _, paragraph in ipairs(paragraphs) do
            if paragraph.sentences and #paragraph.sentences > 0 then
                return true
            end
        end
    end
    return false
end

local function _apply_speaker_prefix(text, speaker, opts)
    if speaker == nil then
        return text
    end
    if opts.include_speakers == false then
        return text
    end
    return "Speaker " .. tostring(speaker) .. ": " .. text
end

local function segments(data, opts)
    opts = _get_opts(opts)
    local source = opts.source or "auto"
    local words = _collect_words(data, opts)

    if source == "auto" then
        if _has_utterances(data) then
            source = "utterances"
        elseif _has_sentences(data) then
            source = "sentences"
        else
            source = "words"
        end
    end

    if source == "utterances" then
        local utterance_segments = _segments_from_utterances(data, opts)
        if #utterance_segments > 0 then
            return utterance_segments
        end
        source = "sentences"
    end

    if source == "sentences" then
        local sentence_segments = _segments_from_sentences(data, opts, words)
        if #sentence_segments > 0 then
            return sentence_segments
        end
        source = "words"
    end

    if source == "paragraphs" then
        local paragraph_segments = _segments_from_paragraphs(data, opts, words)
        if #paragraph_segments > 0 then
            return paragraph_segments
        end
        source = "sentences"
    end

    if source == "words" then
        return _segments_from_words(data, opts)
    end

    return {}
end

local function _segments_to_text(seg_list, opts, separator)
    local items = {}
    for _, segment in ipairs(seg_list) do
        local text = segment.text or ""
        text = _apply_speaker_prefix(text, segment.speaker, opts)
        table.insert(items, text)
    end
    return table.concat(items, separator)
end

local function words_text(data, opts)
    opts = _get_opts(opts)
    opts.source = "words"
    local segs = segments(data, opts)
    local separator = opts.separator or " "
    return _segments_to_text(segs, opts, separator)
end

local function sentences_text(data, opts)
    opts = _get_opts(opts)
    opts.source = "sentences"
    local segs = segments(data, opts)
    local separator = opts.separator or "\n"
    return _segments_to_text(segs, opts, separator)
end

local function paragraphs_text(data, opts)
    opts = _get_opts(opts)
    opts.source = "paragraphs"

    local channels = _get_channel_alternatives(data, opts)
    for _, entry in ipairs(channels) do
        local alt = entry.alternative or {}
        local para = alt.paragraphs
        if para and para.transcript then
            return para.transcript
        end
    end

    local segs = segments(data, opts)
    local separator = opts.separator or "\n"
    return _segments_to_text(segs, opts, separator)
end

local function utterances_text(data, opts)
    opts = _get_opts(opts)
    opts.source = "utterances"
    local segs = segments(data, opts)
    local separator = opts.separator or "\n"
    return _segments_to_text(segs, opts, separator)
end

local function text(data, opts)
    opts = _get_opts(opts)
    local segs = segments(data, opts)
    local separator = opts.separator or "\n"
    return _segments_to_text(segs, opts, separator)
end

local function _find_best_word_window(words, quote_tokens, opts)
    local token_count = #quote_tokens
    if token_count == 0 then
        return nil
    end

    local window_slop = opts.window_slop or 2
    local algorithm = opts.algorithm or "ratio"
    local threshold = opts.threshold or 0.8
    local quote_text = table.concat(quote_tokens, " ")

    local best = nil
    local min_len = math.max(1, token_count - window_slop)
    local max_len = token_count + window_slop

    for window_len = min_len, max_len do
        for i = 1, (#words - window_len + 1) do
            local parts = {}
            for j = i, (i + window_len - 1) do
                local normalized = words[j].normalized
                if normalized == nil or normalized == "" then
                    normalized = _normalize_text(words[j].text or "")
                end
                table.insert(parts, normalized)
            end
            local candidate = table.concat(parts, " ")
            local score = similarity.calculate_similarity(candidate, quote_text, algorithm)
            if best == nil or score > best.score then
                best = {
                    score = score,
                    start_index = i,
                    length = window_len,
                }
            end
        end
    end

    if best == nil or best.score < threshold then
        return nil
    end

    return best
end

local function _window_to_quote(words, window)
    local start_idx = window.start_index
    local end_idx = window.start_index + window.length - 1
    local parts = {}
    local window_words = {}

    for idx = start_idx, end_idx do
        local word = words[idx]
        table.insert(parts, word.text)
        table.insert(window_words, word)
    end

    local start_word = words[start_idx]
    local end_word = words[end_idx]

    return {
        text = table.concat(parts, " "),
        start = start_word and start_word.start,
        ["end"] = end_word and end_word["end"],
        speaker = _select_speaker(window_words),
        channel = start_word and start_word.channel,
    }
end

local function _fuzzy_quote(data, request)
    local opts = _get_opts(request)
    local words = _collect_words(data, opts)
    local quote_tokens = _tokenize_words(request.quote or "")
    local window = _find_best_word_window(words, quote_tokens, opts)
    if window == nil then
        return nil
    end
    local result = _window_to_quote(words, window)
    result.confidence = window.score
    result.method = "fuzzy"
    return result
end

local function _llm_quote(data, request)
    if request.client == nil then
        error("quote.llm requires request.client")
    end

    local text_value = text(data, {source = "auto", include_speakers = false, separator = " "})
    local prompt = "Wrap the exact quote \"" .. tostring(request.quote or "") .. "\" in <span> tags. Return only the updated markup."

    local extract_request = {
        text = text_value,
        client = request.client,
        prompt_template = prompt,
    }

    if request.mock_marked_up_text ~= nil then
        extract_request.mock_marked_up_text = request.mock_marked_up_text
    end

    local result = biblicus.extract(extract_request)
    local spans = result.spans or {}
    if #spans == 0 then
        return nil
    end

    local span_text = spans[1].text or ""
    local words = _collect_words(data, request)
    local window = _find_best_word_window(words, _tokenize_words(span_text), request)
    if window == nil then
        return nil
    end

    local out = _window_to_quote(words, window)
    out.confidence = window.score
    out.method = "llm"
    return out
end

local function quote(data, request)
    if request == nil then
        error("quote requires request table")
    end
    if request.quote == nil then
        error("quote requires request.quote")
    end

    local method = request.method or "auto"
    if method == "fuzzy" then
        return _fuzzy_quote(data, request)
    end

    if method == "llm" then
        return _llm_quote(data, request)
    end

    if method == "auto" then
        local fuzzy = _fuzzy_quote(data, request)
        if fuzzy ~= nil then
            return fuzzy
        end
        if request.client ~= nil then
            return _llm_quote(data, request)
        end
        return nil
    end

    error("unknown quote method: " .. tostring(method))
end

return {
    words_text = words_text,
    sentences_text = sentences_text,
    paragraphs_text = paragraphs_text,
    utterances_text = utterances_text,
    text = text,
    segments = segments,
    quote = quote,
}
