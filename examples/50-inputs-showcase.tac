-- Input Types Showcase
-- Demonstrates all supported input types for GUI and CLI testing

Specification([[
Feature: Inputs showcase

  Scenario: Uses defaults and greets user
    Given the procedure has started
    And the input user_name is "Ada"
    When the procedure runs
    Then the output message should be "Hello Ada!"
    And the output settings should exist
]])

Procedure {
    input = {
            -- String input (required)
            user_name = field.string{required = true, description = "Your name for personalization"},
            -- Number input with default
            repeat_count = field.number{description = "Number of times to repeat the greeting", default = 3},
            -- Boolean input
            formal = field.boolean{description = "Use formal greeting style", default = false},
            -- Array input
            topics = field.array{description = "List of topics to mention", default = {}},
            -- Object input
            preferences = field.object{description = "User preferences as JSON object", default = {}},
            -- Enum input
            language = field.string{default = "english", description = "Language for the greeting"}
    },
    output = {
            message = field.string{required = true, description = "The generated greeting message"},
            settings = field.object{required = true, description = "Summary of settings used"}
    },
    function(input)

    -- Select greeting based on formality and language
        local greetings = {
            english = input.formal and "Dear" or "Hello",
            spanish = input.formal and "Estimado" or "Hola",
            french = input.formal and "Cher" or "Bonjour",
            german = input.formal and "Sehr geehrte/r" or "Hallo"
        }

        local greeting = greetings[input.language] or greetings.english
        local name = input.user_name

        -- Build message
        local message = greeting .. " " .. name .. "!"

        -- Build settings summary
        local settings = {
            name = name,
            language = input.language,
            formal = input.formal,
            repeat_count = input.repeat_count,
            topic_count = 0,
            has_preferences = false
        }

        -- Access preferences if provided (using pairs for Python dict)
        for k, v in pairs(input.preferences or {}) do
            settings.has_preferences = true
            break
        end

        -- Count topics (using pairs since Python list)
        for k, v in pairs(input.topics or {}) do
            settings.topic_count = settings.topic_count + 1
        end

        return {
            message = message,
            settings = settings
        }

    end
}
