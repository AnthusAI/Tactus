# Instructions for Coding Agents

This document provides guidelines for AI coding agents working on the Tactus project.

## Reference Documentation

- **[SPECIFICATION.md](SPECIFICATION.md)**: The official specification for the Tactus domain-specific language. Refer to this document for the definitive guide on DSL syntax, semantics, and behavior.
- **[IMPLEMENTATION.md](IMPLEMENTATION.md)**: Maps the specification to the actual codebase implementation. Shows where each feature is implemented, what's complete, and what's missing relative to the specification. Use this to understand the current implementation status when working on features.

## Production Readiness

**IMPORTANT**: Tactus is **NOT** ready for production. It is in early development (Alpha status).

### Do NOT:
- Declare that Tactus is "ready for production"
- Claim that features are "production-ready"
- State that the project is "complete" or "finished"
- Use phrases like "ready to use in production" or "production-ready"

### Do:
- Focus on testing and verification
- Run existing tests before declaring changes complete
- Verify that implementations actually work as intended
- Acknowledge limitations and incomplete features
- Suggest improvements and note areas that need work

## Testing Requirements

Before declaring any change complete:

1. **Run existing tests**: Use `pytest` to verify no regressions
2. **Test the specific feature**: Create or update tests for new functionality
3. **Verify imports**: Ensure all imports resolve correctly
4. **Check for errors**: Run linters and fix any issues

## Code Quality

- Follow existing code patterns and style
- Add appropriate logging for debugging
- Include docstrings for public APIs
- Handle errors gracefully with proper exception types
- Keep implementations simple and maintainable

## Project Status

Tactus is a standalone workflow engine extracted from a larger project. It is:
- In active development
- Missing some features (noted in code with TODO comments)
- Subject to API changes
- Not yet suitable for production use

When working on Tactus, focus on:
- Making incremental improvements
- Fixing bugs and issues
- Adding missing functionality
- Improving documentation
- Writing and maintaining tests


