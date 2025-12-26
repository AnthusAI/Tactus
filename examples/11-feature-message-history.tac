-- Message History Demo
-- Demonstrates using the MessageHistory primitive to manage conversation history
-- Aligned with pydantic-ai's message_history concept

agent("chatbot", {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = "You are a helpful chatbot. Answer questions concisely.",
})

-- Procedure with message_history configuration
main = procedure("main", {
    input = {
        user_message = {
            type = "string",
            default = "Hello, how are you?"
        }
    },
    output = {
        response = {
            type = "string",
            required = true
        },
        history_length = {
            type = "number",
            required = true
        }
    },
    state = {},

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
        content = input.user_message
    })
    
    -- Have the agent respond
    Chatbot.turn()
    
    -- Get the conversation history (message_history in pydantic-ai terms)
    local history = MessageHistory.get()

    -- Count messages (Python list doesn't support # operator in Lua)
    local count = 0
    for _, msg in python.iter(history) do
        count = count + 1
        Log.info("Message " .. count, {role = msg.role, content = msg.content})
    end

    Log.info("Conversation history", {length = count})
    
    -- Clear history if needed
    -- MessageHistory.clear()
    
    return {
        response = "Conversation completed",
        history_length = count
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
