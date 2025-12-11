# AI Agent Guidelines

## Semantic Release & Versioning

This project uses **semantic-release** for automated versioning and releases.

### Commit Message Format (Conventional Commits)

- `feat:` → MINOR version bump (0.1.0 → 0.2.0) - use sparingly
- `fix:` → PATCH version bump (0.1.0 → 0.1.1)
- `docs:`, `test:`, `chore:`, `refactor:`, `style:` → No version bump

### Important: Version Escalation Awareness

**Do NOT use `feat:` for every new feature.** Be conscious of version escalation:

- Group related changes into meaningful releases
- Use `chore:` or `refactor:` for internal improvements that don't add user-facing features
- Reserve `feat:` for significant new capabilities that warrant a minor version bump
- Consider if the change truly adds value that users should know about in the changelog

### Examples

**Good:**
```
feat: add AWS Bedrock provider support
fix: handle missing config file gracefully
chore: update dependencies
refactor: simplify error handling logic
```

**Avoid:**
```
feat: add helper function           # Use chore:
feat: improve internal logic        # Use refactor:
feat: add logging statement         # Use chore:
```

### Release Process

Releases happen automatically on push to main. The CI runs:
1. Linting (ruff), formatting (black)
2. Tests (pytest + behave, excluding integration tests)
3. Semantic-release (if tests pass)
4. Publishes to PyPI

Monitor with: `gh run watch`
