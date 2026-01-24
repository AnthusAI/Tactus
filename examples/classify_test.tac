-- Simple test to verify Classify is available

Procedure {
    output = {
        result = field.string{required = true}
    },
    function(input)
        -- Test if Classify exists
        if Classify == nil then
            error("Classify is nil!")
        end

        print("Classify is available!")
        print("Type: " .. type(Classify))

        -- Try to create a simple fuzzy classifier
        print("Creating fuzzy classifier with expected='test'...")
        local matcher = Classify {
            method = "fuzzy",
            expected = "test",
            threshold = 0.8
        }

        print("Classifier created successfully!")
        print("Matcher type: " .. type(matcher))

        -- Test matching
        local result = matcher("test")
        print("Match result: " .. result.value)
        print("Confidence: " .. tostring(result.confidence))

        return {result = "Success"}
    end
}
