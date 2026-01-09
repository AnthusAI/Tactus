# Agent Instructions for Code Development

## Test Responsibility

**ALL failing tests are within scope. Fix every single one.**

When working on code changes:
- Every test failure is your responsibility to fix
- No test is "out of scope" or an "edge case" you can skip
- Don't stop until ALL tests pass (pytest, BDD, integration, etc.)
- Don't summarize remaining failures as "edge cases" - fix them
- Test failures are not optional follow-up work - they're blocking issues

If tests fail:
1. Read the error message carefully
2. Identify the root cause
3. Fix the code or test
4. Verify the fix by running tests again
5. Repeat until ALL tests pass

**"The remaining failures are edge cases" = Wrong approach**
**"All tests now pass" = Correct completion**
