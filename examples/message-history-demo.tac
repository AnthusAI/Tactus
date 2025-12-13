-- Message History Demo
-- Demonstrates using the MessageHistory primitive to manage conversation history
-- Aligned with pydantic-ai's message_history concept

agent("chatbot", {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = "You are a helpful chatbot. Answer questions concisely.",
    tools = {"done"}
})

-- Procedure with message_history configuration
procedure({
    params = {
        user_message = {
            type = "string",
            default = "Hello, how are you?"
        }
    },
    outputs = {
        response = {
            type = "string",
            required = true
        },
        history_length = {
            type = "number",
            required = true
        }
    },
    
    -- Procedure-level message_history config (aligned with pydantic-ai)
    message_history = {
        mode = "isolated",  -- Each agent gets its own history
        max_tokens = 120000
    }
}, function()
    Log.info("Message history demo starting")
    
    -- Manually add a user message to the message history
    MessageHistory.inject_system("You are having a friendly conversation")
    MessageHistory.append({
        role = "user",
        content = params.user_message
    })
    
    -- Have the agent respond
    Chatbot.turn()
    
    -- Get the conversation history (message_history in pydantic-ai terms)
    local history = MessageHistory.get()
    Log.info("Conversation history", {length = #history})
    
    -- Log each message
    for i, msg in ipairs(history) do
        Log.info("Message " .. i, {role = msg.role, content = msg.content})
    end
    
    -- Clear history if needed
    -- MessageHistory.clear()
    
    return {
        response = "Conversation completed",
        history_length = #history
    }
end)

-- BDD Specifications
specifications([[
Feature: Message History Management
  Demonstrate message history manipulation (aligned with pydantic-ai)

  Scenario: Message history tracks messages
    Given the procedure has started
    When the procedure runs
    Then the procedure should complete successfully
    And the output history_length should exist
]])
