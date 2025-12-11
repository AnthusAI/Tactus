-- Migrated from .tyml format to .tactus.lua

name("multi_model_example")
version("1.0.0")
description("Example showing multiple OpenAI models in one procedure")

-- Parameters
parameter("topic", {
    type = "string",
    default = "artificial intelligence",
})

-- Agents
agent("researcher", {
    provider = "openai",
    model = "gpt-4o",
    system_prompt = [[You are a researcher. Research the topic: {params.topic}
Provide comprehensive findings.
When done, call the done tool.
]],
    initial_message = "Please research the topic.",
    tools = {"done"},
})

agent("summarizer", {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[You are a summarizer. Create a concise summary.
When done, call the done tool.
]],
    initial_message = "Please summarize the research.",
    tools = {"done"},
})

-- Procedure
procedure(function()
    -- Research phase with GPT-4o
    Log.info("Starting research with GPT-4o...")
    repeat
      Researcher.turn()
    until Tool.called("done")

    local research = Tool.last_call("done").args.reason
    State.set("research", research)

    -- Summarization phase with GPT-4o-mini
    Log.info("Creating summary with GPT-4o-mini...")
    repeat
      Summarizer.turn()
    until Tool.called("done")

    local summary = Tool.last_call("done").args.reason

    return {
      research = research,
      summary = summary,
      models_used = {"gpt-4o", "gpt-4o-mini"}
    }

end)
