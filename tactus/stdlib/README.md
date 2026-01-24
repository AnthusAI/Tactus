# Tactus Standard Library

The Tactus standard library provides reusable primitives for building AI agents and classification workflows.

## Architecture

The stdlib follows the **Dogfooding with BDD Specs as Contract** principle:

1. **BDD specs define behavior** - Each primitive has comprehensive `.spec.tac` files
2. **Implementation is secondary** - Python, Tactus, or mix - doesn't matter if specs pass
3. **Specs serve triple duty** - Tests, documentation, and contract

## Structure

```
tactus/stdlib/
├── classify/
│   ├── classify.tac          # Tactus implementation (reference)
│   ├── classify.spec.tac     # BDD specifications (THE CONTRACT)
│   ├── primitive.py           # Current Python implementation
│   ├── llm.py                 # LLM-based classifier
│   └── fuzzy.py               # Fuzzy string matching
```

## Testing

Run all stdlib specs:
```bash
tactus stdlib test
```

Run specific primitive specs:
```bash
tactus test tactus/stdlib/classify/classify.spec.tac
```

## Documentation

Each `.spec.tac` file contains:
- `--[[doc]]` blocks with usage documentation
- `--[[doc:parameter name]]` blocks with parameter documentation
- BDD scenarios showing expected behavior
- Custom step definitions for the tests

## Example: Classify

The Classify primitive demonstrates the stdlib pattern:

**Specifications** ([classify.spec.tac](classify/classify.spec.tac)):
- 7 BDD scenarios covering LLM and fuzzy matching
- Documentation blocks explaining usage and parameters
- Custom steps for testing classification behavior

**Current Status**:
- ✅ Specs pass with Python implementation
- ✅ Tactus reference implementation exists
- 🔜 Module loading system needed to use Tactus impl

## Adding New Primitives

1. Create `primitive-name/` directory
2. Write `primitive-name.spec.tac` with:
   - `--[[doc]]` documentation blocks
   - Custom step definitions
   - Comprehensive BDD scenarios
3. Implement in Python (for now) or Tactus (when module loading ready)
4. Ensure `tactus test` passes

## CI Integration

```yaml
# .github/workflows/stdlib.yml
- name: Test Standard Library
  run: tactus stdlib test --verbose
```

All stdlib specs must pass before merge.
