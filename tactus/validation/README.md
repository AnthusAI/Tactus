# Tactus DSL Validation

This module provides ANTLR-based validation for `.tac` files.

## Architecture

The validation system uses a three-phase approach:

```
.tac file
      ↓
Phase 1: ANTLR Parsing (Lua 5.4 grammar)
      ↓
   Parse Tree
      ↓
Phase 2: Semantic Visitor (DSL pattern recognition)
      ↓
   Registry with Declarations
      ↓
Phase 3: Registry Validation (cross-reference checking)
      ↓
   ValidationResult
```

### Key Components

1. **ANTLR Grammar** (`grammar/LuaLexer.g4`, `grammar/LuaParser.g4`)
   - Standard Lua 5.4 grammar from antlr/grammars-v4
   - Unmodified - semantic layer added on top
   - Same grammar generates both Python and TypeScript parsers

2. **Generated Parsers** (`generated/`)
   - `LuaLexer.py` / `LuaParser.py` - Python parser
   - `LuaLexer.ts` / `LuaParser.ts` - TypeScript parser
   - Generated from grammar using ANTLR4
   - Committed to version control

3. **Semantic Visitor** (`semantic_visitor.py`)
   - Walks ANTLR parse tree
   - Recognizes DSL function calls (name, parameter, agent, etc.)
   - Extracts arguments and builds registry
   - Does NOT execute code

4. **Validator** (`validator.py`)
   - Main entry point for validation
   - Coordinates parsing, semantic analysis, and registry validation
   - Supports quick (syntax only) and full (semantic) modes

## Validation Modes

### Quick Mode
- ANTLR parse only
- Catches syntax errors
- Fast (suitable for IDE real-time validation)
- Returns immediately after syntax check

### Full Mode
- ANTLR parse + semantic analysis + registry validation
- Catches syntax errors, DSL errors, and semantic errors
- Slower but thorough
- Used by CLI and pre-execution validation

## Usage

### Python

```python
from tactus.validation import TactusValidator, ValidationMode

validator = TactusValidator()

# Quick validation (syntax only)
result = validator.validate(source, ValidationMode.QUICK)

# Full validation (syntax + semantics)
result = validator.validate(source, ValidationMode.FULL)

if result.valid:
    print(f"Valid! Procedure: {result.registry.procedure_name}")
else:
    for error in result.errors:
        print(f"Error at {error.location}: {error.message}")
```

### CLI

```bash
# Validate a file
tactus validate examples/01-basics-hello-world.tac

# Quick validation (syntax only)
tactus validate examples/01-basics-hello-world.tac --quick
```

## Parser Generation

### Requirements

**Docker is REQUIRED** for parser generation:
- ANTLR4 requires Java Runtime
- We use Docker to avoid Java installation
- Image: `eclipse-temurin:17-jre`

### Regenerating Parsers

**When to regenerate:**
- Only when modifying grammar files
- Generated parsers are committed to repo
- End users don't need to regenerate

**How to regenerate:**

```bash
# Ensure Docker is running
make generate-parsers

# Or individually:
make generate-python-parser
make generate-typescript-parser
```

### Manual Generation

**Python:**
```bash
docker run --rm \
  -v $(pwd):/work \
  -v /tmp:/tmp \
  -w /work \
  eclipse-temurin:17-jre \
  java -jar /tmp/antlr-4.13.1-complete.jar \
  -Dlanguage=Python3 \
  -visitor \
  -no-listener \
  -o /work/tactus/validation/generated \
  /work/tactus/validation/grammar/LuaLexer.g4 \
  /work/tactus/validation/grammar/LuaParser.g4

# Fix 'this' references (ANTLR bug)
sed -i 's/this\./self./g' tactus/validation/generated/LuaParser.py
sed -i 's/this\./self./g' tactus/validation/generated/LuaLexer.py
```

**TypeScript:**
```bash
docker run --rm \
  -v $(pwd):/work \
  -w /work/tactus-web \
  eclipse-temurin:17-jre \
  bash -c "
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - &&
    apt-get install -y nodejs &&
    npm install &&
    npx antlr4ts -visitor -no-listener \
      -o src/validation/generated \
      /work/tactus/validation/grammar/LuaLexer.g4 \
      /work/tactus/validation/grammar/LuaParser.g4
  "
```

## Testing

### Python Tests

```bash
pytest tests/validation/test_antlr_parser.py -v
```

Tests cover:
- Valid/invalid Lua syntax
- Error location reporting
- DSL function recognition
- Parameter/output/agent extraction
- All example files
- Missing required fields
- Quick vs full mode

### TypeScript Tests

```bash
cd tactus-web && npm test
```

**Note:** TypeScript parser currently has compilation issues due to antlr4ts code generation bugs. This is being addressed.

## Known Issues

### TypeScript Parser
The antlr4ts code generator has known issues:
- Generates code with TypeScript compilation errors
- Base class imports need manual fixes
- Some generated code references don't match antlr4ts API

**Workaround:** Python parser is fully functional and used for all validation. TypeScript parser is in progress.

## Why ANTLR?

1. **Formal Grammar** - Standard Lua 5.4 grammar, not custom
2. **Multi-Language** - Same grammar generates Python and TypeScript parsers
3. **No Execution** - Validates without running code
4. **IDE Support** - Parse tree enables syntax highlighting, autocomplete, etc.
5. **Accurate** - Catches all Lua syntax errors
6. **Maintainable** - Grammar is separate from implementation

## Separation of Concerns

- **Validation (ANTLR)**: Parse tree analysis, no execution
- **Runtime (lupa)**: Actual Lua execution with primitives

The same `.tac` file works for both:
- ANTLR validates structure
- lupa executes the procedure











