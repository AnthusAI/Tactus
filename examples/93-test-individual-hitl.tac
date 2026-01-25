--[[
Test Individual HITL Request Types

This example tests each HITL request type individually, in order of
implementation status. The working types come first so you can test
them without being blocked by unimplemented features.

Run with: tactus run examples/93-test-individual-hitl.tac
--]]

Procedure {
    function(input)
        print("Testing Individual HITL Request Types")

        -- ===== WORKING REQUEST TYPES =====

        -- Test 1: Approval (IMPLEMENTED)
        print("\n=== TEST 1: APPROVAL (Simple) ===")
        local deploy_approved = Human.approve("Deploy v1.0.0 to production?")
        print("Deployment approved: " .. tostring(deploy_approved))

        if not deploy_approved then
            print("Deployment cancelled by user.")
            return {completed = false, reason = "deployment_cancelled"}
        end

        -- Test 2: Text Input (IMPLEMENTED)
        print("\n=== TEST 2: TEXT INPUT ===")
        local deployment_notes = Human.input({
            message = "Enter deployment notes:",
            default = "Production deployment"
        })
        print("Deployment notes: " .. deployment_notes)

        -- Test 3: Single Select (IMPLEMENTED)
        print("\n=== TEST 3: SINGLE SELECT ===")
        local target_env = Human.select({
            message = "Select target environment:",
            options = {"dev", "staging", "prod"},
            mode = "single"
        })
        print("Target environment: " .. target_env)

        -- Test 4: Multiple Select (IMPLEMENTED)
        print("\n=== TEST 4: MULTIPLE SELECT ===")
        local features = Human.select({
            message = "Which features should be enabled?",
            options = {"dark_mode", "notifications", "analytics", "beta_features"},
            mode = "multiple",
            min = 1
        })

        -- Handle both string (single selection) and table (multiple selections)
        local features_str = ""
        if type(features) == "table" then
            features_str = table.concat(features, ", ")
        else
            features_str = tostring(features)
        end
        print("Selected features: " .. features_str)

        -- Test 5: Approval with Timeout (IMPLEMENTED)
        print("\n=== TEST 5: APPROVAL WITH TIMEOUT ===")
        local timed_approval = Human.approve({
            message = "Quick approval needed (30 second timeout)",
            timeout = 30,
            default = false
        })
        print("Timed approval: " .. tostring(timed_approval))

        print("\n=== ALL WORKING TESTS COMPLETE ===")
        print("Summary:")
        print("  Deployment approved: " .. tostring(deploy_approved))
        print("  Notes: " .. deployment_notes)
        print("  Target: " .. target_env)
        print("  Features: " .. features_str)
        print("  Timed approval: " .. tostring(timed_approval))

        return {
            completed = true,
            deployment_approved = deploy_approved,
            notes = deployment_notes,
            target = target_env,
            features = features,
            features_str = features_str,
            timed_approval = timed_approval
        }
    end
}
