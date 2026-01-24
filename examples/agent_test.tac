-- Test if Agent is available during execution

Procedure {
    output = {
        result = field.string{required = true}
    },
    function(input)
        print("Checking if Agent is available...")
        if Agent == nil then
            error("Agent is nil!")
        end
        print("Agent is available! Type: " .. type(Agent))

        print("Checking if Classify is available...")
        if Classify == nil then
            error("Classify is nil!")
        end
        print("Classify is available! Type: " .. type(Classify))

        return {result = "Both Agent and Classify are available"}
    end
}
