-- Input Types Showcase
-- Demonstrates all supported input types for GUI and CLI testing

main = procedure("main", {
    input = {
        -- String input (required)
        user_name = {
            type = "string",
            required = true,
            description = "Your name for personalization"
        },

        -- Number input with default
        repeat_count = {
            type = "number",
            default = 3,
            description = "Number of times to repeat the greeting"
        },

        -- Boolean input
        formal = {
            type = "boolean",
            default = false,
            description = "Use formal greeting style"
        },

        -- Array input
        topics = {
            type = "array",
            default = {},
            description = "List of topics to mention"
        },

        -- Object input
        preferences = {
            type = "object",
            default = {},
            description = "User preferences as JSON object"
        },

        -- Enum input
        language = {
            type = "string",
            default = "english",
            enum = {"english", "spanish", "french", "german"},
            description = "Language for the greeting"
        }
    },
    output = {
        message = {
            type = "string",
            required = true,
            description = "The generated greeting message"
        },
        settings = {
            type = "object",
            required = true,
            description = "Summary of settings used"
        }
    },
    state = {}
}, function()
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
end)
