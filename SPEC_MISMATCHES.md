# Specification Mismatches

This document tracks all identified mismatches between the SPECIFICATION.md and the current implementation. Each mismatch is tagged in the feature files with `@spec_mismatch` and a descriptive tag.

## Summary

- **Total Mismatches Found**: 10
- **Critical (Breaks Spec Contract)**: 6
- **Documentation Gaps**: 1
- **Status**: All documented and tagged for future fixes

---

## 1. Parameter Enum Validation Not Enforced at Runtime

**Tag**: `@enum_not_validated_at_runtime`  
**File**: `features/20_parameters.feature:87`  
**Severity**: Medium

### Specification Says (lines 112-114):
```yaml
params:
  depth:
    type: string
    enum: [shallow, deep]
```

### Current Behavior:
- Registry stores enum values in `ParameterDeclaration.enum`
- Validation only checks enum at parse time
- Runtime does NOT validate parameter values against enum constraints

### Fix Required:
- **File**: `tactus/core/runtime.py`
- **Action**: Add parameter validation before procedure execution
- **Implementation**: Check params against registry.parameters[name].enum if defined

---

## 2. Output Schema Validation Not Enforced at Runtime

**Tag**: `@output_validation_not_enforced`  
**File**: `features/21_outputs.feature:92`  
**Severity**: High

### Specification Says (lines 152-158):
> When `outputs:` is present:
> 1. Required fields are validated to exist
> 2. Types are checked
> 3. Only declared fields are returned (internal data stripped)

### Current Behavior:
- Registry stores output schema in `registry.outputs`
- Runtime does NOT validate return values against output schema
- All fields are returned without filtering

### Fix Required:
- **File**: `tactus/core/runtime.py`
- **Action**: Add output validation after procedure returns
- **Implementation**: 
  1. Validate required fields exist
  2. Check types match declarations
  3. Filter return dict to only include declared fields

---

## 3. Custom Prompts Not Used at Runtime

**Tag**: `@prompts_not_used_at_runtime`  
**Files**: 
- `features/28_custom_prompts.feature:10` (return_prompt)
- `features/28_custom_prompts.feature:32` (error_prompt)
- `features/28_custom_prompts.feature:54` (status_prompt)

**Severity**: High

### Specification Says:

#### return_prompt (lines 165-175):
> Injected when the procedure completes successfully. The agent does one final turn to generate a summary, which becomes the return value.

#### error_prompt (lines 177-187):
> Injected when the procedure fails (exception or max iterations exceeded). The agent explains what went wrong.

#### status_prompt (lines 189-199):
> Injected when a caller requests a status update (async procedures only). The agent reports current progress without stopping.

### Current Behavior:
- Registry stores all three prompts in `registry.return_prompt`, `registry.error_prompt`, `registry.status_prompt`
- Runtime does NOT inject these prompts at appropriate times
- Procedures return raw values without prompt-guided summarization

### Fix Required:
- **File**: `tactus/core/runtime.py`
- **Actions**:
  1. On successful completion: inject return_prompt, get agent summary, use as return value
  2. On exception: inject error_prompt, get agent explanation, include in error
  3. On status request: inject status_prompt, get progress report, return to caller

---

## 4. Async Execution Not Implemented

**Tag**: `@async_not_implemented`  
**File**: `features/29_execution_settings.feature:10`  
**Severity**: Critical

### Specification Says (lines 218-232):
```yaml
# Enable async invocation (caller can spawn and continue)
async: true
```

> Procedures run identically in two execution contexts:
> - Local Execution Context (polling loop, manual resume)
> - Lambda Durable Execution Context (native suspend/resume)

### Current Behavior:
- Registry stores `async_enabled` flag
- Runtime does NOT implement async execution
- All procedures run synchronously
- No spawn/continue capability
- No checkpoint/resume for async procedures

### Fix Required:
- **File**: `tactus/core/runtime.py`
- **Action**: Implement async execution modes
- **Implementation**:
  1. Add `Procedure.spawn()` primitive for async invocation
  2. Implement checkpoint/resume for local context
  3. Add polling loop for pending async procedures
  4. Support Lambda Durable Execution context abstraction

---

## 5. Session Filters Not Applied at Runtime

**Tag**: `@filters_not_used_at_runtime`  
**Files**:
- `features/30_session_filters.feature:10` (last_n)
- `features/30_session_filters.feature:34` (token_budget)
- `features/30_session_filters.feature:58` (by_role)
- `features/30_session_filters.feature:82` (compose)

**Severity**: Medium

### Specification Says (lines 828-834):
```yaml
agents:
  researcher:
    session:
      filter:
        class: ComposedFilter
        chain:
          - class: TokenBudget
            max_tokens: 120000
```

### Current Behavior:
- DSL defines filter functions: `filters.last_n()`, `filters.token_budget()`, `filters.by_role()`, `filters.compose()`
- Filters return tuples that can be stored in agent session config
- Runtime does NOT apply filters to agent conversation history
- All messages are passed to agents without filtering

### Fix Required:
- **File**: `tactus/core/runtime.py`
- **Action**: Apply session filters when building agent context
- **Implementation**:
  1. Parse filter tuples from agent.session.filter
  2. Apply filters to message history before agent turn
  3. Support composed filters (chain multiple filters)

---

## 6. Matchers Not Documented in Specification

**Tag**: `@matchers_not_documented_in_spec`  
**Files**:
- `features/31_matchers.feature:10` (contains)
- `features/31_matchers.feature:33` (equals)
- `features/31_matchers.feature:56` (matches)

**Severity**: Low (Documentation Gap)

### Current Behavior:
- Implementation provides three matcher functions in `dsl_stubs.py`:
  - `contains(pattern)` - string contains matcher
  - `equals(value)` - equality matcher
  - `matches(regex)` - regex matcher
- Matchers return tuples: `("contains", pattern)`, `("equals", value)`, `("matches", regex)`

### Specification Status:
- **NOT DOCUMENTED** in SPECIFICATION.md
- No description of what matchers are or how to use them
- No examples of matcher usage

### Fix Required:
- **File**: `SPECIFICATION.md`
- **Action**: Add "Matchers" section documenting these functions
- **Content Needed**:
  1. Purpose of matchers (pattern matching in workflows)
  2. Available matchers and their syntax
  3. Example usage in procedure code
  4. How matchers integrate with validation/assertions

---

## Impact Analysis

### High Priority (Breaks Spec Contract)
1. **Output Schema Validation** - Spec promises validation, implementation doesn't deliver
2. **Custom Prompts** - Spec describes behavior, implementation doesn't execute
3. **Async Execution** - Core feature described in spec, not implemented

### Medium Priority (Partial Implementation)
4. **Parameter Enum Validation** - Feature exists but not enforced
5. **Session Filters** - Functions defined but not applied

### Low Priority (Documentation)
6. **Matchers** - Feature works but undocumented

---

## Testing Strategy

All mismatches are tagged with `@spec_mismatch` in feature files. To run only mismatch scenarios:

```bash
behave --tags=@spec_mismatch
```

To exclude mismatch scenarios from CI:

```bash
behave --tags=-@spec_mismatch
```

---

## Next Steps

1. **Prioritize fixes** based on severity and user impact
2. **Create GitHub issues** for each mismatch with links to this document
3. **Update IMPLEMENTATION.md** to reflect current status
4. **Remove @spec_mismatch tags** as fixes are implemented
5. **Re-run all features** to verify fixes don't break existing functionality

---

## Notes

- All feature specs pass validation (syntax checking)
- Mismatches are behavioral, not syntactic
- Implementation is internally consistent, just differs from spec
- Spec may need updates to match implementation decisions

