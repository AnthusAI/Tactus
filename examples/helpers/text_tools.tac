-- Helper file: Text processing tools
-- This file defines tools that can be imported by other .tac files

uppercase = Tool {
    description = "Convert text to uppercase",
    input = {
        text = field.string{required = true, description = "Text to convert"}
    },
    function(args)
        return args.text:upper()
    end
}

lowercase = Tool {
    description = "Convert text to lowercase",
    input = {
        text = field.string{required = true, description = "Text to convert"}
    },
    function(args)
        return args.text:lower()
    end
}

reverse = Tool {
    description = "Reverse the text",
    input = {
        text = field.string{required = true, description = "Text to reverse"}
    },
    function(args)
        return string.reverse(args.text)
    end
}

word_count = Tool {
    description = "Count words in text",
    input = {
        text = field.string{required = true, description = "Text to analyze"}
    },
    function(args)
        local count = 0
        for word in string.gmatch(args.text, "%S+") do
            count = count + 1
        end
        return string.format("%d words", count)
    end
}

-- Define a toolset that groups these tools
Toolset "text_processing" {
    tools = {"uppercase", "lowercase", "reverse", "word_count"}
}