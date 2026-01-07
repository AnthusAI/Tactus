-- Standard done tool from Tactus stdlib
-- Signals completion of a task

Tool "done" {
    description = "Signal task completion",
    input = {
        reason = field.string{
            required = true,
            description = "Reason for completion"
        }
    },
    output = {
        status = field.string{
            required = true,
            description = "Completion status"
        }
    },
    function(input)
        return {status = "Completed: " .. input.reason}
    end
}