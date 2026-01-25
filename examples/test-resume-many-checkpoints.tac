--[[
Test: Many Checkpoints (Scale Test)

This test verifies that checkpoint/resume works correctly with many checkpoints,
testing both scale and the ability to resume from any position.

Run with: tactus run examples/test-resume-many-checkpoints.tac --storage file --storage-path /tmp/tactus-test-many --no-sandbox
--]]

function main()
    print("=== Many Checkpoints Test ===")
    print("")

    local results = {}
    local num_iterations = 10

    for i = 1, num_iterations do
        print("Iteration " .. i .. " of " .. num_iterations)

        local approved = Human.approve({
            message = "Approve iteration " .. i .. "?",
            default = true
        })

        print("  Result: " .. tostring(approved))
        table.insert(results, approved)

        if not approved then
            print("  User declined at iteration " .. i .. ". Stopping.")
            return {
                completed_iterations = i,
                stopped_at = i,
                results = results,
                test = "many-checkpoints-stopped"
            }
        end
    end

    print("")
    print("=== Test Complete ===")
    print("All " .. num_iterations .. " iterations completed!")

    return {
        completed_iterations = num_iterations,
        results = results,
        test = "many-checkpoints-complete"
    }
end
