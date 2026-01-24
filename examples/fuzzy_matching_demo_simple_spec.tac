-- Fuzzy Matching Classifier Demo with Simple BDD Spec
-- Demonstrates all algorithm options: ratio, token_set_ratio, token_sort_ratio, partial_ratio

Procedure {
    output = {
        summary = field.string{required = true, description = "Demo execution summary"}
    },
    function(input)
        -- School names we're trying to match
        local SCHOOLS = {
            "United Education Institute",
            "Abilene Christian University",
            "Arizona School of Integrative Studies",
        }

        print("Running fuzzy matching tests...")

        -- Test 1: token_set_ratio (best for reordered words)
        local classifier1 = Classify {
            method = "fuzzy",
            classes = SCHOOLS,
            threshold = 0.65,
            algorithm = "token_set_ratio"
        }

        local result1 = classifier1("Institute Education United")
        assert(result1.value == "United Education Institute", "token_set_ratio should match reordered tokens")
        assert(result1.matched_text == "United Education Institute", "matched_text should be populated")
        assert(result1.confidence == 1.0, "Perfect match should have confidence 1.0")
        print("✓ token_set_ratio test passed")

        -- Test 2: Binary mode
        local classifier2 = Classify {
            method = "fuzzy",
            expected = "United Education Institute",
            threshold = 0.7,
            algorithm = "token_set_ratio"
        }

        local result2 = classifier2("Institute Education United Dallas")
        assert(result2.value == "Yes", "Binary mode should return Yes for match")
        assert(result2.matched_text == "United Education Institute", "matched_text should be the expected value")
        print("✓ Binary mode test passed")

        -- Test 3: No match returns nil matched_text
        local result3 = classifier2("Florida Technical College")
        assert(result3.value == "No", "Binary mode should return No for non-match")
        assert(result3.matched_text == nil, "matched_text should be nil on no match")
        print("✓ No match test passed")

        -- Test 4: partial_ratio algorithm
        local classifier4 = Classify {
            method = "fuzzy",
            classes = {"Florida Technical College"},
            threshold = 0.70,
            algorithm = "partial_ratio"
        }

        local result4 = classifier4("Florida Tech College")
        assert(result4.matched_text and string.find(result4.matched_text, "Florida"),
            "partial_ratio should match shortened names")
        print("✓ partial_ratio test passed")

        return {summary = "All fuzzy matching tests passed"}
    end
}

-- Simple BDD specification that tests the whole procedure
Specification([[
Feature: Fuzzy String Matching

  Scenario: Demo runs all fuzzy matching tests successfully
    Given the procedure has started
    When the procedure runs
    Then the procedure should complete successfully
    And the output summary should be "All fuzzy matching tests passed"
]])
