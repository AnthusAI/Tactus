-- HITL Toolset for Agent-Driven Human Approval
--
-- Provides a simple approval tool that agents can use to request
-- human approval dynamically.

return {
    name = "hitl_approval",
    description = "Tools for requesting human input and approval",

    tools = {
        {
            name = "ask_approval",
            description = "Ask the human for deployment approval. Pass a clear message describing what needs approval.",
            input = {
                message = field.string{required = true, description = "The approval question to ask the human"}
            },
            handler = function(args)
                Log.info("[Agent → Human] Asking for approval: " .. args.message)

                -- Use Human.approve() to get approval
                local approved = Human.approve({
                    message = args.message
                })

                Log.info("[Human → Agent] Approval response: " .. tostring(approved))

                return {
                    approved = approved,
                    message = "Human " .. (approved and "approved" or "rejected") .. " the request"
                }
            end
        }
    }
}
