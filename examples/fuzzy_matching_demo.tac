-- Fuzzy Matching Classifier Demo
-- Demonstrates all algorithm options: ratio, token_set_ratio, token_sort_ratio, partial_ratio
-- Real-world use case: Matching school names with variations

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
            "California Institute of Arts and Technology",
            "Florida Technical College"
        }

        -- Test inputs with various formats/variations
        local TEST_INPUTS = {
            "United Education Institute - Dallas",
            "Institute Education United",  -- Reordered tokens
            "UEI College Dallas",  -- Abbreviation + extra words
            "Abilene Christian",  -- Partial name
            "Christian University Abilene",  -- Reordered
            "Arizona Integrative Studies School",  -- Reordered + slight variation
            "California Arts and Technology Institute",  -- Reordered
            "Florida Tech College",  -- Shortened word
            "Technical College in Florida"  -- Reordered
        }

        print("=" .. string.rep("=", 79))
        print("FUZZY MATCHING CLASSIFIER - COMPREHENSIVE DEMO")
        print("=" .. string.rep("=", 79))
        print()

        -- Helper function to print results nicely
        local function print_result(input_text, result, algorithm)
            local status = result.value ~= "NO_MATCH" and "✓ MATCHED" or "✗ NO MATCH"
            print(string.format("  Input: '%s'", input_text))
            print(string.format("  %s: %s", status, result.value))
            if result.matched_text then
                print(string.format("  Matched: '%s'", result.matched_text))
            end
            print(string.format("  Confidence: %.1f%%", (result.confidence or 0) * 100))
            print(string.format("  Algorithm: %s", algorithm))
            print()
        end

        --------------------------------------------------------------------------------
        -- Demo 1: ratio (default) - Character-level similarity
        --------------------------------------------------------------------------------
        print("Demo 1: 'ratio' Algorithm (Character-Level Similarity)")
        print("-" .. string.rep("-", 79))
        print("Best for: Exact or near-exact matches")
        print("How it works: Compares character-by-character similarity")
        print()

        local ratio_matcher = Classify {
            method = "fuzzy",
            classes = SCHOOLS,
            threshold = 0.75,
            algorithm = "ratio"  -- Character-level similarity (default)
        }

        for _, input_text in ipairs(TEST_INPUTS) do
            local result = ratio_matcher(input_text)
            print_result(input_text, result, "ratio")
        end

        print()

        --------------------------------------------------------------------------------
        -- Demo 2: token_set_ratio - Handles reordered tokens
        --------------------------------------------------------------------------------
        print("Demo 2: 'token_set_ratio' Algorithm (Token Set Comparison)")
        print("-" .. string.rep("-", 79))
        print("Best for: Reordered words, extra words")
        print("How it works: Compares unique tokens (words) regardless of order")
        print()

        local token_set_matcher = Classify {
            method = "fuzzy",
            classes = SCHOOLS,
            threshold = 0.65,  -- Lower threshold for token-based matching
            algorithm = "token_set_ratio"
        }

        for _, input_text in ipairs(TEST_INPUTS) do
            local result = token_set_matcher(input_text)
            print_result(input_text, result, "token_set_ratio")
        end

        print()

        --------------------------------------------------------------------------------
        -- Demo 3: token_sort_ratio - Sorts tokens before comparing
        --------------------------------------------------------------------------------
        print("Demo 3: 'token_sort_ratio' Algorithm (Token Sort Comparison)")
        print("-" .. string.rep("-", 79))
        print("Best for: Reordered words with same token counts")
        print("How it works: Sorts all tokens alphabetically before comparing")
        print()

        local token_sort_matcher = Classify {
            method = "fuzzy",
            classes = SCHOOLS,
            threshold = 0.65,
            algorithm = "token_sort_ratio"
        }

        for _, input_text in ipairs(TEST_INPUTS) do
            local result = token_sort_matcher(input_text)
            print_result(input_text, result, "token_sort_ratio")
        end

        print()

        --------------------------------------------------------------------------------
        -- Demo 4: partial_ratio - Best substring match
        --------------------------------------------------------------------------------
        print("Demo 4: 'partial_ratio' Algorithm (Partial String Match)")
        print("-" .. string.rep("-", 79))
        print("Best for: Shortened names, partial text")
        print("How it works: Finds best matching substring")
        print()

        local partial_matcher = Classify {
            method = "fuzzy",
            classes = SCHOOLS,
            threshold = 0.70,
            algorithm = "partial_ratio"
        }

        for _, input_text in ipairs(TEST_INPUTS) do
            local result = partial_matcher(input_text)
            print_result(input_text, result, "partial_ratio")
        end

        print()

        --------------------------------------------------------------------------------
        -- Demo 5: Binary Mode - Yes/No matching against single expected value
        --------------------------------------------------------------------------------
        print("Demo 5: Binary Mode (Yes/No Matching)")
        print("-" .. string.rep("-", 79))
        print("Use case: Check if input matches a specific expected value")
        print()

        local binary_matcher = Classify {
            method = "fuzzy",
            expected = "United Education Institute",
            threshold = 0.70,
            algorithm = "token_set_ratio"
        }

        local binary_tests = {
            "United Education Institute",  -- Exact match
            "Institute Education United Dallas",  -- Reordered with extra
            "UEI College",  -- Abbreviation
            "Florida Technical College"  -- Different school
        }

        for _, input_text in ipairs(binary_tests) do
            local result = binary_matcher(input_text)
            local status = result.value == "Yes" and "✓ YES" or "✗ NO"
            print(string.format("  Input: '%s'", input_text))
            print(string.format("  %s (confidence: %.1f%%)", status, (result.confidence or 0) * 100))
            if result.matched_text then
                print(string.format("  Expected: '%s'", result.matched_text))
            end
            print()
        end

        print()

        --------------------------------------------------------------------------------
        -- Demo 6: Algorithm Comparison - Same input, different algorithms
        --------------------------------------------------------------------------------
        print("Demo 6: Algorithm Comparison (Same Input, All Algorithms)")
        print("-" .. string.rep("-", 79))
        print("Input: 'Institute Education United Dallas'")
        print()

        local test_input = "Institute Education United Dallas"
        local algorithms = {"ratio", "token_set_ratio", "token_sort_ratio", "partial_ratio"}
        local thresholds = {0.75, 0.65, 0.65, 0.70}

        for i, algo in ipairs(algorithms) do
            local matcher = Classify {
                method = "fuzzy",
                classes = SCHOOLS,
                threshold = thresholds[i],
                algorithm = algo
            }

            local result = matcher(test_input)
            print(string.format("Algorithm: %-20s | Match: %-35s | Confidence: %.1f%%",
                algo,
                result.matched_text or "NO_MATCH",
                (result.confidence or 0) * 100
            ))
        end

        print()

        --------------------------------------------------------------------------------
        -- Demo 7: Practical Use Case - School Name Validation
        --------------------------------------------------------------------------------
        print("Demo 7: Practical Use Case - School Name Validation in Metadata")
        print("-" .. string.rep("-", 79))
        print()

        -- Simulate processing metadata with various school name formats
        local metadata_samples = {
            {school = "United Education Institute - Dallas Campus", expected = "United Education Institute"},
            {school = "Abilene Christian", expected = "Abilene Christian University"},
            {school = "Arizona ISSP", expected = "Arizona School of Integrative Studies"},
            {school = "California Institute Arts Tech", expected = "California Institute of Arts and Technology"}
        }

        local validator = Classify {
            method = "fuzzy",
            classes = SCHOOLS,
            threshold = 0.65,
            algorithm = "token_set_ratio"  -- Best for variations
        }

        print("Validating school names from metadata:")
        print()

        for _, sample in ipairs(metadata_samples) do
            local result = validator(sample.school)
            local matched = result.value ~= "NO_MATCH"
            local correct = result.matched_text == sample.expected

            print(string.format("  Metadata: '%s'", sample.school))
            print(string.format("  Expected: '%s'", sample.expected))
            print(string.format("  Matched:  '%s'", result.matched_text or "NO_MATCH"))
            print(string.format("  Status:   %s (%.1f%% confidence)",
                correct and "✓ CORRECT" or (matched and "⚠ WRONG MATCH" or "✗ NO MATCH"),
                (result.confidence or 0) * 100
            ))
            print()
        end

        print()

        --------------------------------------------------------------------------------
        -- Summary and Recommendations
        --------------------------------------------------------------------------------
        print("=" .. string.rep("=", 79))
        print("SUMMARY & RECOMMENDATIONS")
        print("=" .. string.rep("=", 79))
        print()

        print([[
Algorithm Selection Guide:

1. ratio (default):
   - Use for: Exact or near-exact matches
   - Pros: Fast, simple, good for typos
   - Cons: Poor with reordered words or extra text
   - Threshold: 0.75-0.85

2. token_set_ratio (recommended for school names):
   - Use for: Variations with reordered/extra words
   - Pros: Handles "Institute Education United" = "United Education Institute"
   - Cons: Doesn't handle abbreviations well
   - Threshold: 0.65-0.75

3. token_sort_ratio:
   - Use for: Similar to token_set_ratio
   - Pros: Good for reordered words
   - Cons: More strict than token_set_ratio
   - Threshold: 0.65-0.75

4. partial_ratio:
   - Use for: Shortened names, substrings
   - Pros: Finds "Tech" in "Technical College"
   - Cons: Can match too loosely
   - Threshold: 0.70-0.80

For CMG-EDU school name matching:
  → Use token_set_ratio with threshold 0.65-0.75
  → For abbreviations (UEI, ASIS), add explicit aliases

Note: Pure abbreviations like "UEI" won't match "United Education Institute"
      because they share no tokens. Consider maintaining an abbreviation map.
]])

        print()
        print("=" .. string.rep("=", 79))

        return {summary = "Fuzzy matching demo completed successfully"}
    end
}

-- BDD Specification - validates that the demo runs successfully
Specification([[
Feature: Fuzzy String Matching with Multiple Algorithms

  Scenario: Comprehensive demo runs all fuzzy matching tests
    Given the procedure has started
    When the procedure runs
    Then the procedure should complete successfully
    And the output summary should be "Fuzzy matching demo completed successfully"
]])
