# Model Primitive: First-Class MLOps Integration (Roadmap)

For current usage and syntax, see `docs/model-primitive.md`.

NOTE: This roadmap includes historical sketches (including older Lua calling
styles like `:predict(...)`). The canonical DSL pattern is to call models like
functions and unwrap with:

```lua
local result = Model("name")({ ... })
local out = result.output or result
```

## Vision

The Tactus `Model` primitive becomes the integration point between AI procedure development and MLOps infrastructure. It separates **prediction** (pure input-to-output transformation) from **generation/decision-making** (conversational, multi-turn agents), giving each its own first-class language construct with distinct semantics, tooling, and lifecycle.

### Why This Matters

1. **Static analysis**: Parse a `.tac` file and know what ML resources it needs without running it. CI/CD can pre-provision infrastructure, validate credentials, estimate costs.
2. **MLOps integration**: Model registry, versioning, champion/challenger promotion, training hooks, monitoring -- all through a standard interface.
3. **DevOps clarity**: Models are external resources that need provisioning, just like agents need API credentials. Both should be declarative and visible in the parse tree.
4. **Conceptual clarity**: Agent = conversation (multi-turn, tools, decisions). Model = prediction (stateless, cacheable, composable). Different things, different primitives.

---

## Current State

### What Exists

- `ModelPrimitive` class (tactus/primitives/model.py) with automatic checkpointing
- `ModelBackend` protocol (tactus/backends/model_backend.py) defining `predict()` / `predict_sync()`
- Two backends: `HTTPModelBackend` and `PyTorchModelBackend`
- DSL syntax: `classifier = Model "name" { type = "pytorch", ... }`
- Input/output schema fields parsed but **not validated**
- Mock support for testing
- Checkpoint type `"model_predict"` for durability

### What's Wrong

- **Stdlib ignores it**: `LLMClassifier` (tactus/stdlib/tac/tactus/classify/llm.tac) uses `Agent` for classification, bypassing the model interface entirely
- **No stdlib modules use the model primitive**
- **No working .tac examples**: `examples/models/` has only a README and a Python script
- **Schemas are decorative**: `input_schema` and `output_schema` are stored but never validated
- **No registry, versioning, training, or cost tracking**
- **Only two backend types**: `http` and `pytorch`

---

## Design Principles

1. **Declarative over imperative**: Model declarations should be static and analyzable
2. **Backend-agnostic**: The same model name can be backed by PyTorch, an HTTP endpoint, an LLM, or a registry-resolved artifact
3. **Schema-enforced**: Pydantic validates inputs and outputs at the boundary
4. **Registry-native**: Models are versioned artifacts with champion/challenger semantics
5. **Cost-aware**: Track inference cost where applicable (LLM token costs, API call costs, compute time)
6. **Trainable**: First-class training hooks for models that support it
7. **Composable**: Models can be used inside procedures, steps, and other models (ensembles)

---

## Developer Experience

### Scenario: Adding a Binary Text Classifier

**Step 1: Declare in your procedure**

```lua
-- my-workflow.tac
Model "urgent_classifier" {
    type = "registry",
    name = "urgent-classifier",
    version = "champion",

    input = { text = "string" },
    output = { label = "string", confidence = "float" },

    fallback = {
        type = "llm",
        provider = "openai",
        model = "gpt-4o-mini",
        prompt = "Is this feedback urgent? Respond 'urgent' or 'not_urgent': {text}"
    }
}

	procedure "process_feedback" {
	    function run(input)
	        local result = Model("urgent_classifier")({text = input.feedback})
	        local out = result.output or result
	        if out.label == "urgent" then
	            -- escalate
	        end
	    end
	}
```

**Step 2: Define training configuration (same Model block)**

```lua
-- my-workflow.tac
Model "urgent-classifier" {
    type = "registry",
    name = "urgent-classifier",
    version = "latest",

    input = { text = "string" },
    output = { label = "string", confidence = "float" },

    training = {
        data = {
            train = "data/urgent-train.jsonl",
            val = "data/urgent-val.jsonl",
            test = "data/urgent-test.jsonl"
        },

        candidates = {
            {
                name = "llm-zeroshot",
                trainer = "llm",
                hyperparameters = {
                    provider = "openai",
                    model = "gpt-4o-mini",
                    prompt = "Classify: {text}"
                }
            },
            {
                name = "sklearn-svm",
                trainer = "sklearn",
                hyperparameters = {
                    script = "models/urgent-classifier/train_svm.py"
                }
            },
            {
                name = "pytorch-bert",
                trainer = "pytorch",
                hyperparameters = {
                    script = "models/urgent-classifier/train_bert.py",
                    learning_rate = 2e-5,
                    epochs = 3
                }
            }
        }
    }
}
```

**Step 3: Train and evaluate**

```bash
tactus train my-workflow.tac --model urgent-classifier
tactus models evaluate my-workflow.tac --model urgent-classifier

# Output:
# Model              Version                 Count  Accuracy  Precision  Recall  F1
# urgent-classifier  candidate/pytorch-bert  2000   0.93      0.91       0.95    0.93
```

**Step 4: Promote champion**

```bash
tactus models promote urgent-classifier --candidate pytorch-bert --tag champion
```

**Step 5: Production uses champion automatically**

The procedure's `version = "champion"` resolves to the promoted model. No code changes.

---

## Architecture

### Component Overview

```
.tac file (model declaration)
        |
        v
    DSL Parser --> Static analysis (resource extraction)
        |
        v
    ModelPrimitive
        |
        +-- Schema validation (Pydantic)
        |
        +-- Backend resolution
        |       |
        |       +-- RegistryBackend --> ModelRegistry protocol
        |       |       |
        |       |       +-- LocalRegistry (filesystem/S3)
        |       |       +-- MLflowRegistry
        |       |       +-- SageMakerRegistry
        |       |       +-- CustomRegistry
        |       |
        |       +-- LLMBackend (new)
        |       +-- HTTPModelBackend (exists)
        |       +-- PyTorchModelBackend (exists)
        |       +-- SKLearnBackend (new)
        |       +-- ONNXBackend (new)
        |       +-- CustomBackend
        |
        +-- Cost tracking
        |
        +-- Checkpointing (exists)
        |
        +-- Mock support (exists)
```

### ModelRegistry Protocol

```python
class ModelRegistry(Protocol):
    def resolve(self, name: str, version: str) -> ModelArtifact:
        """Resolve name+version to a loadable artifact."""

    def list_versions(self, name: str) -> list[ModelVersion]:
        """List all versions of a model."""

    def promote(self, name: str, version: str, tag: str) -> None:
        """Tag a version (e.g., 'champion', 'staging')."""

    def log_prediction(self, model_id: str, input: Any, output: Any,
                       cost: float | None, latency_ms: float) -> None:
        """Log prediction for monitoring."""
```

### Storage Protocol

```python
class ModelStorage(Protocol):
    def save(self, artifact: bytes, path: str) -> str:
        """Save model artifact, return URI."""

    def load(self, uri: str) -> bytes:
        """Load model artifact from URI."""

    def exists(self, uri: str) -> bool:
        """Check if artifact exists."""
```

Implementations: `LocalStorage`, `S3Storage`, `GCSStorage`.

### Cost Tracking

```python
@dataclass
class PredictionCost:
    """Cost of a single prediction."""
    inference_cost: float | None = None    # Dollar cost (LLM tokens, API calls)
    compute_time_ms: float | None = None   # Wall clock time
    tokens_in: int | None = None           # Input tokens (LLM only)
    tokens_out: int | None = None          # Output tokens (LLM only)

    @property
    def total_cost(self) -> float | None:
        return self.inference_cost
```

Cost tracking is **only applicable for some model types**:
- **LLM backends**: Token-based cost from provider pricing
- **HTTP backends**: Could track per-call cost if configured
- **PyTorch/sklearn/ONNX**: No per-prediction cost (compute is local)

The model primitive returns an enriched result:

```python
@dataclass
class PredictionResult:
    """Result from a model prediction."""
    output: Any                            # The actual prediction
    cost: PredictionCost | None = None     # Cost info (if applicable)
    model_version: str | None = None       # Which version was used
    backend_type: str | None = None        # Which backend ran it
```

### Training Infrastructure

```python
class ModelTrainer(Protocol):
    def train(self, config: TrainingConfig, data: DataConfig) -> TrainedArtifact:
        """Train a model from config and data."""

    def evaluate(self, artifact: TrainedArtifact, test_data: str) -> EvalMetrics:
        """Evaluate a trained model."""
```

Training is orchestrated by CLI commands, not by the runtime. The runtime only does inference.

---

## Unresolved Design Questions

### 1. LLM Backend: Internal Implementation

**Question**: When an LLM is used as a model backend (e.g., zero-shot classification), what can the backend use internally?

**Answer**: The Model primitive defines the **interface contract** (stateless `predict()`, schema-validated, checkpointed, cost-tracked), not the implementation. A backend is free to use whatever it needs internally -- including an Agent with a full conversation loop and retry feedback.

For example, an LLM-based classifier may genuinely need an agentic conversation: send classification prompt, parse response, send correction feedback if invalid, retry. That's an Agent inside a Model, and that's fine. The caller still sees `predict()` and gets back a result.

- A PyTorch backend's implementation is `torch.forward()`
- An HTTP backend's implementation is a POST request
- An LLM backend's implementation may be an Agent with retry logic

All three present the same `predict()` interface. The separation between Model and Agent is about the **contract to the caller**, not about restricting what's inside the box.

### 2. Schema Definition: Pydantic in .tac or in Python?

**Question**: Where do input/output schemas live?

**Option A**: Inline in `.tac` files as simple type declarations:
```lua
Model "classifier" {
    input = { text = "string" },
    output = { label = "string", confidence = "float" }
}
```
Runtime generates Pydantic models from these declarations.

**Option B**: Reference Python Pydantic models:
```lua
Model "classifier" {
    input = "myproject.schemas.ClassifierInput",
    output = "myproject.schemas.ClassifierOutput"
}
```

**Option C**: Support both -- simple inline for common cases, Python reference for complex validation.

**Recommendation**: Option C. Simple inline schemas cover 80% of cases. Python references handle complex validation (regex patterns, cross-field validation, custom validators).

### 3. Registry Scope: Per-Project or Shared?

**Question**: Is the model registry local to a project or shared across projects?

**Option A**: Per-project only (models stored in `models/` directory or project S3 prefix).
- Pro: Simple, no coordination needed
- Con: Can't share models across projects

**Option B**: Shared registry (MLflow server, SageMaker, etc.) with per-project configuration.
- Pro: Standard MLOps pattern, model reuse
- Con: Requires infrastructure

**Option C**: Local by default, configurable to use shared registries.

**Recommendation**: Option C. Local filesystem registry for development and small projects. Configuration to point at MLflow/SageMaker/etc. for production. The `ModelRegistry` protocol abstracts this.

### 4. How Does Cost Flow Back to the Caller?

**Question**: The `predict()` method currently returns the raw prediction. How do we return cost data without breaking the simple interface?

**Option A**: Always return `PredictionResult` wrapper with `.output` and `.cost`:
```lua
local result = Model("classifier")({text = "hello"})
local out = result.output or result
print(result.output.label)   -- "urgent"
print(result.cost.tokens_in) -- 42
```

**Option B**: Return raw output by default, opt-in to enriched result:
```lua
-- Simple (default)
local result = Model("classifier")({text = "hello"})
local out = result.output or result
local label = out.label or out

-- Enriched
local result = classifier:predict_with_metadata({text = "hello"})
print(result.output)
print(result.cost)
```

**Option C**: Return raw output, accumulate costs on the model object:
```lua
local classifier = Model("classifier")
local result = classifier({text = "hello"})
local out = result.output or result
local label = out.label or out
print(classifier.last_cost)
print(classifier.total_cost)
```

**Recommendation**: Option A, but with Lua metatable sugar so `result.label` works as a shortcut for `result.output.label` when you don't care about cost. This keeps the simple case simple while making cost always available.

### 5. Training Data Format

**Question**: What format should training data be in?

**Option A**: JSONL only (one JSON object per line).
**Option B**: Support JSONL, CSV, TSV, Parquet.
**Option C**: Training data format is the training script's concern, not Tactus's.

**Recommendation**: Option C. Tactus passes file paths to training scripts. The scripts handle their own data loading. Tactus only needs to know where the data lives for provenance tracking.

### 6. Candidate Comparison: Built-in or External?

**Question**: Should Tactus build evaluation/comparison tooling or delegate to MLflow/Weights & Biases/etc.?

**Option A**: Built-in evaluation with CLI output (tables, basic metrics).
**Option B**: Delegate entirely to external tools.
**Option C**: Built-in basic evaluation, export to external tools for deep analysis.

**Recommendation**: Option C. `tactus models evaluate` produces a summary table and structured JSON. Users can pipe that to MLflow, W&B, or whatever they use. Tactus doesn't need to build dashboards.

### 7. How Does Fallback Work?

**Question**: When `version = "champion"` but no champion exists yet (new project, first deployment), what happens?

**Option A**: Error. Require explicit champion before running.
**Option B**: Use `fallback` config if provided, error if not.
**Option C**: Use fallback silently.

**Recommendation**: Option B. Fallback is explicit and logged. If no fallback and no champion, fail clearly with instructions on how to train and promote.

### 8. Model Primitive vs. Classify/Extract Stdlib

**Question**: Once models are first-class, what happens to the existing `tactus.classify` and `tactus.extract` stdlib modules?

**Option A**: Rewrite them to use model primitive internally.
**Option B**: Keep them as-is (agent-based), add new model-based alternatives.
**Option C**: Deprecate them in favor of model primitive usage.

**Recommendation**: Option A for the long term. Short term, keep both working. The stdlib classify/extract modules become convenience wrappers around model predictions, not standalone agent-based implementations.

### 9. How Are Models Discovered by Static Analysis?

**Question**: If a procedure uses `require()` to load a module that internally declares a model, can static analysis still find it?

This is the same problem agents have. Any resource declaration nested inside runtime logic is invisible to static analysis.

**Recommendation**: Document that top-level model declarations are statically analyzable. Models declared inside functions or conditionals are not. Encourage top-level declarations. Consider a `tactus models list my-procedure.tac` command that does both static extraction and optional runtime discovery.

### 10. Versioning Semantics

**Question**: What does "version" mean exactly?

- A specific trained artifact (`pytorch-bert-20260212-143022`)
- A semantic version (`v2.1.0`)
- A tag (`champion`, `staging`, `latest`)
- A git commit SHA

**Recommendation**: Support all of these. Tags are mutable pointers (like git tags). Artifact IDs are immutable. Semantic versions are optional labels. The registry resolves any of these to a concrete artifact.

---

## Implementation Plan

### Phase 0: Foundation (Schema Validation)

Make the existing model primitive actually validate its inputs and outputs.

**0.1** Add Pydantic schema generation from inline `.tac` declarations
- Parse `input = { text = "string" }` into a Pydantic model at runtime
- Location: `tactus/primitives/model.py`
- Test: Model with schema rejects invalid input

**0.2** Validate inputs in `predict()`
- Before calling backend, validate `input_data` against `input_schema`
- Return clear error message on validation failure
- Test: Invalid input raises `ValidationError` with field-level detail

**0.3** Validate outputs from backends
- After backend returns, validate against `output_schema`
- Log warning on schema mismatch (don't fail -- backends may be external)
- Test: Backend returning wrong shape logs warning

**0.4** Support Python Pydantic model references
- Allow `input = "myproject.schemas.MyInput"` syntax
- Import and use the referenced Pydantic model
- Test: Python Pydantic model used for validation

### Phase 1: LLM Backend

Enable LLM-powered predictions through the model interface.

**1.1** Create `LLMModelBackend` class
- Location: `tactus/backends/llm_backend.py`
- Internally uses an Agent with conversation loop for classification
- Agent handles prompt construction, response parsing, retry-with-feedback
- Presents `predict()` interface: caller sees input in, result out
- Uses existing LLM/Agent infrastructure (provider/model config)
- Test: LLM backend returns classification result

**1.2** Add `type = "llm"` to model primitive routing
- Update `_create_backend()` in `model.py`
- Test: `Model "x" { type = "llm", ... }` creates LLMModelBackend

**1.3** Configurable retry behavior
- Optional `retries` and `retry_prompt` config passed to internal Agent
- Caller still sees single `predict()` call regardless of retry count
- Test: Invalid LLM response triggers internal retry, caller gets clean result

**1.4** Add cost tracking to LLM backend
- Track input/output tokens from LLM response
- Calculate cost based on provider pricing
- Return cost in prediction result
- Test: Prediction result includes token counts and cost estimate

**1.5** Add `.tac` example: LLM-based classification via model primitive
- `examples/models/llm-classification.tac`
- Test: Example runs successfully with `--mock`

### Phase 2: Cost Tracking

**2.1** Define `PredictionCost` and `PredictionResult` data classes
- Location: `tactus/primitives/model.py` or new `tactus/models/types.py`
- Test: Data classes serialize/deserialize correctly

**2.2** Update `ModelPrimitive.predict()` to return `PredictionResult`
- Wrap backend output in result object
- Include timing (wall clock)
- Test: All existing tests still pass (backward compat via metatable/proxy)

**2.3** Add cost accumulation on model instance
- `model.total_cost`, `model.prediction_count`, `model.avg_latency_ms`
- Test: After N predictions, accumulated stats are correct

**2.4** Add cost tracking to HTTP backend
- Optional `cost_per_call` config field
- Test: HTTP predictions accumulate configured cost

**2.5** Expose cost in Lua
- `result.cost.tokens_in`, `result.cost.inference_cost`, etc.
- `classifier.total_cost` for accumulated cost
- Test: Lua code can access cost fields

### Phase 3: Local Model Registry

**3.1** Define `ModelRegistry` protocol
- Location: `tactus/registry/protocol.py`
- Methods: `resolve`, `list_versions`, `promote`, `log_prediction`
- Test: Protocol is implementable

**3.2** Implement `LocalRegistry` (filesystem-based)
- Location: `tactus/registry/local.py`
- Storage: `~/.tactus/models/` or project-local `models/`
- Metadata in JSON sidecar files
- Test: Save, list, resolve, promote operations work

**3.3** Add `type = "registry"` to model primitive
- Resolves model name + version/tag through registry
- Falls back to `fallback` config if resolution fails
- Test: Registry-backed model resolves to correct backend

**3.4** Implement champion/challenger tagging
- `promote(name, version, tag)` updates tag pointer
- `champion-previous` auto-tag for rollback
- Test: Promote updates tag, old champion becomes previous

**3.5** Add `tactus models list` CLI command
- List models declared in a `.tac` file (static analysis)
- List versions in registry for a model name
- Test: CLI output matches expected format

**3.6** Add `tactus models promote` CLI command
- `tactus models promote <name> --candidate <version> --tag champion`
- Test: CLI promotion updates registry

### Phase 4: S3 Storage Backend

**4.1** Define `ModelStorage` protocol
- Location: `tactus/registry/storage.py`
- Methods: `save`, `load`, `exists`, `list`
- Test: Protocol is implementable

**4.2** Implement `LocalStorage`
- Filesystem-based, for development
- Test: Save and load model artifacts locally

**4.3** Implement `S3Storage`
- Uses boto3
- Supports `s3://bucket/key` URIs
- Test: Integration test with mocked S3 (moto)

**4.4** Wire storage into registry
- Registry uses storage protocol for artifact persistence
- Test: Local registry can use either local or S3 storage

**4.5** Support `path = "s3://..."` shorthand in model config
- `Model "x" { type = "pytorch", path = "s3://bucket/model.pt" }`
- Downloads to local cache on first use
- Test: S3 path resolves and caches locally

### Phase 5: Training Infrastructure

**5.1** Define `TrainingConfig` and `EvalMetrics` data classes
- Location: `tactus/training/types.py`
- Test: Data classes validate correctly

**5.2** Implement training runner
- Executes training scripts as subprocesses
- Passes hyperparameters as CLI args or config file
- Captures metrics from stdout/file
- Test: Training script executes and metrics are captured

**5.3** Implement evaluation runner
- Runs trained model against test dataset
- Computes accuracy, precision, recall, F1
- Outputs comparison table
- Test: Evaluation produces correct metrics

**5.4** Add `tactus train` CLI command
- `tactus train config.tac [--model name] [--candidate name]`
- Test: CLI trains candidate and saves artifact

**5.5** Add `tactus models evaluate` CLI command
- `tactus models evaluate config.tac --model <name> [--version|--candidate]`
- Outputs metrics table + JSON for the resolved registry version
- Test: CLI evaluates the selected version and shows metrics

**5.6** Support candidate definitions in training config
- Parse `training.candidates = { ... }` from `.tac` file
- Train/evaluate each independently
- Test: Multiple candidates train and evaluate

### Phase 6: Stdlib Alignment

**6.1** Create `tactus.models.llm` stdlib module
- Convenience wrapper around model primitive with `type = "llm"`
- Test: Module loads and creates LLM-backed model

**6.2** Refactor `LLMClassifier` to use model primitive internally
- Keep existing API (`LLMClassifier:new{...}`, `:classify()`)
- Delegate to model primitive under the hood
- Test: All existing classify tests still pass

**6.3** Update stdlib README
- Document model primitive usage
- Show model-based classification alongside agent-based
- Test: README examples are accurate

**6.4** Add model-based examples
- `examples/models/classification.tac` - Full classification workflow
- `examples/models/http-endpoint.tac` - HTTP model usage
- `examples/models/registry-usage.tac` - Registry with champion
- Test: All examples run with `--mock`

### Phase 7: External Registry Integration

**7.1** Implement `MLflowRegistry`
- Location: `tactus/registry/mlflow.py`
- Test: Integration test with mocked MLflow

**7.2** Implement `SageMakerRegistry`
- Location: `tactus/registry/sagemaker.py`
- Test: Integration test with mocked SageMaker

**7.3** Add registry configuration to project config
- Allow `.tactus/config.toml` or similar to specify default registry
- Test: Project-level registry config is respected

### Phase 8: Advanced Features

**8.1** Model ensembles ✅
- Combine multiple model predictions (vote/average)
- Test: Ensemble model produces combined result

**8.2** A/B testing support ✅
- Route percentage of traffic to challenger model
- Log which version handled each prediction (arm_index metadata)
- Test: Traffic split matches configured percentages

**8.3** Data drift detection ✅
- Compare production input distribution against training data
- Alert when drift exceeds threshold (rolling detector)
- Test: Drift detector flags synthetic drift

**8.4** Automatic retraining triggers ✅
- Schedule-based or metric-based retraining
- Test: Retrain triggered when accuracy drops below threshold

---

## Migration Path

### Backward Compatibility

All existing code continues to work unchanged:
- Current `Model "name" { type = "http"|"pytorch", ... }` syntax unchanged
- `LLMClassifier` via Agent continues to work
- No forced migration

### Recommended Migration

1. **Immediate**: Add Pydantic schemas to existing model declarations
2. **Short term**: Use `type = "llm"` for new classification tasks instead of Agent
3. **Medium term**: Move trained models into local registry with versioning
4. **Long term**: Refactor existing Agent-based classifiers to use model primitive

---

## File Organization

```
tactus/
├── primitives/
│   └── model.py              # ModelPrimitive (enhance)
├── backends/
│   ├── model_backend.py      # ModelBackend protocol (exists)
│   ├── http_backend.py       # HTTPModelBackend (exists)
│   ├── pytorch_backend.py    # PyTorchModelBackend (exists)
│   ├── llm_backend.py        # LLMModelBackend (NEW)
│   ├── sklearn_backend.py    # SKLearnModelBackend (NEW, later)
│   └── onnx_backend.py       # ONNXModelBackend (NEW, later)
├── registry/
│   ├── protocol.py           # ModelRegistry protocol (NEW)
│   ├── storage.py            # ModelStorage protocol (NEW)
│   ├── local.py              # LocalRegistry (NEW)
│   ├── s3_storage.py         # S3Storage (NEW)
│   ├── mlflow.py             # MLflowRegistry (NEW, later)
│   └── sagemaker.py          # SageMakerRegistry (NEW, later)
├── training/
│   ├── types.py              # TrainingConfig, EvalMetrics (NEW)
│   ├── runner.py             # TrainingRunner (NEW)
│   └── evaluator.py          # ModelEvaluator (NEW)
├── models/
│   └── types.py              # PredictionCost, PredictionResult (NEW)
├── stdlib/
│   └── tac/tactus/
│       ├── classify/
│       │   └── llm.tac       # Refactor to use model primitive
│       └── models/
│           └── llm.tac       # New stdlib model module (NEW)
└── cli/
    └── app.py                # Add model subcommands
```
