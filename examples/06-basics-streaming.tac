-- Streaming Example
-- Demonstrates real-time LLM response streaming in the Tactus IDE
-- Note: Streaming only works when NO structured outputs are defined

-- Agent with plain text response (enables streaming)
agent("storyteller", {
    provider = "openai",
    system_prompt = [[You are a creative storyteller. 

CRITICAL INSTRUCTIONS:
1. Write ONE short story (about 100 words)
2. IMMEDIATELY call the done tool after writing the story
3. Do NOT write anything after calling done
4. Do NOT ask if the user wants another story
5. Do NOT offer to continue - just call done

The done tool is MANDATORY. Call it as soon as you finish the story.]],
    initial_message = "Tell me a short story about a robot learning to paint. After you write it, call the done tool immediately.",
    tools = {"done"},
})

-- Procedure with NO outputs defined (allows streaming)
procedure(function()
    Log.info("Starting streaming test")

    -- ReAct loop: Keep turning until the agent calls done (max 5 turns)
    -- This allows the agent to generate the story first, then call the tool
    local story_text = ""
    local max_turns = 5
    local turn_count = 0
    
    repeat
      local response = Storyteller.turn()
      turn_count = turn_count + 1
      
      -- Accumulate the story text from each turn using .text property
      if response.text and response.text ~= "" then
        story_text = story_text .. response.text
      end
      
      -- Safety check: exit if too many turns
      if turn_count >= max_turns then
        Log.warn("Max turns reached without done being called")
        break
      end
    until Tool.called("done")

    -- Extract the summary from the done tool call
    local done_summary = "N/A"
    if Tool.called("done") then
      done_summary = Tool.last_call("done").args.reason
      Log.info("Story complete!", {summary = done_summary})
    else
      Log.warn("Story incomplete - done tool not called")
    end
    
    return {
        story = story_text,  -- The actual story text that was streamed
        done_summary = done_summary,  -- What the agent said when calling done
        turns = turn_count,
        success = Tool.called("done")
    }
end)
