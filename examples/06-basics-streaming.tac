-- Streaming Example
-- Demonstrates real-time LLM response streaming in the CLI
-- Note: Streaming only works when NO structured outputs are defined

-- Simple agent that just writes text (no tools needed for streaming demo)
agent("storyteller", {
    provider = "openai",
    system_prompt = [[You are a creative storyteller. Write engaging short stories.

When asked to write a story:
- Write ONE complete story (about 100-150 words)
- Make it vivid and engaging
- End naturally when the story is complete
- Do NOT ask follow-up questions
- Do NOT offer to continue or write more]],
    initial_message = "Write a short story about a robot learning to paint.",
})

-- Simple procedure: one turn to generate and stream the story
procedure(function()
    Log.info("Starting streaming test - watch the text appear in real-time!")

    -- Single turn - the agent writes the complete story
    local response = Storyteller.turn()
    
    -- Check if done tool was called
    if Tool.called("done") then
      local done_summary = Tool.last_call("done").args.reason
      Log.info("Story complete!", {summary = done_summary})
      
      return {
          story = response.text,
          done_summary = done_summary,
          success = true
      }
    else
      -- Story was written but done not called - that's okay for streaming demo
      Log.info("Story written (streaming demonstrated)")
      
      return {
          story = response.text,
          success = true
      }
    end
end)
