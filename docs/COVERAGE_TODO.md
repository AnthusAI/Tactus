# Test Coverage TODO

Current status: 100% coverage on model-related code (excluding protocol.py).

## Files with 100% Coverage ✓
- tactus/backends/http_backend.py ✓
- tactus/models/types.py ✓
- tactus/models/__init__.py ✓ (skip)
- tactus/registry/__init__.py ✓ (skip)

## Files Needing Additional Tests

### tactus/backends/llm_backend.py ✓ (100%)
All lines covered:
- [x] Line 94: Test async predict() method (wrapper for predict_sync)
- [x] Line 115: Test with non-dict input_data (str(input_data) branch)
- [x] Line 130: Test when agent_result.output is string instead of dict
- [x] Lines 190-192: Test parse error when JSON not found at start (parse_direction="start")
- [x] Line 208: Test parse error when JSON not found at end (parse_direction="end")
- [x] Line 162: Unreachable fallback (pragma: no cover)

### tactus/models/schema.py ✓ (100%)
All lines covered:
- [x] Line 67: Test unknown field type (non-string, non-dict) defaults to Any

### tactus/primitives/model.py ✓ (100%)
All lines covered:
- [x] Lines 107-109: Test creating LLM backend
- [x] Line 123: Test unknown model type raises ValueError (existing test)
- [x] Lines 141-154: Test predict() with checkpointing (existing test)
- [x] Lines 183-184: Test input validation with non-dict single-field input
- [x] Lines 193-209: Test with mock_manager (existing tests)
- [x] Lines 221-226: Test LLM backend result format processing
- [x] Line 244: Test output validation with non-dict output
- [x] Line 260: Phantom branch (pragma: no branch) - compute_time_ms is always set
- [x] Lines 263, 270, 275, 280-282: Test cumulative statistics
- [x] Line 297: Test __call__ method (existing test)
- [x] Line 300: __repr__ method (existing test)

### tactus/registry/protocol.py (83.3% - but expected)
Missing lines: 60, 77, 89, 106, 126

These are abstract Protocol methods - they cannot be "covered" by tests since they're not implemented.
This is expected and acceptable. Real implementations (LocalRegistry) will have their own coverage.

## Test Files to Update

1. **tests/models/test_llm_backend.py**
   - Add async test
   - Add non-dict input test
   - Add string output test
   - Add parse error tests

2. **tests/models/test_schema.py**
   - Add test for non-BaseModel class reference

3. **tests/models/test_model_validation.py** or **tests/primitives/test_model.py**
   - Add PyTorch backend test
   - Add unknown type test
   - Add checkpointing test
   - Add mock_manager tests
   - Add __call__ test
   - Add async predict test

## Priority

HIGH PRIORITY (blocks Phase 3 completion):
1. LLM backend tests (6 missing lines)
2. Schema test (1 missing line)
3. Model primitive tests (critical paths)

The protocol.py "missing" coverage is acceptable as it's a Protocol definition.

## Commands

Run coverage:
```bash
coverage erase
coverage run -m pytest tests/backends/test_http_backend.py tests/models/ tests/registry/ -q
coverage combine
coverage report --include="tactus/backends/http_backend.py,tactus/models/*.py,tactus/backends/llm_backend.py,tactus/primitives/model.py,tactus/registry/*.py"
```
