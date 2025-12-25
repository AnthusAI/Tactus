# Tactus Durable Execution Design

## Overview

Tactus provides durable execution for agentic workflows through automatic checkpointing and replay. Unlike graph-based systems that require explicit node definitions, Tactus allows developers to write natural imperative Lua code while automatically handling persistence, interruption, and resumption.

## Core Principles

### Natural Control Flow

Developers write normal Lua code with if/else, loops, and function calls. No special routing syntax or graph definitions required:

```lua
-- customer_support.tactus.lua

-- Sub-procedure for handling escalations
handle_escalation = procedure "handle_escalation" {
    input = {
        issue = {type = "string", required = true},
        history = {type = "array"}
    },
    output = {
        resolution = {type = "string"}
    },
    run = function()
        Supervisor = agent "supervisor" {
            model = "claude-sonnet-4-20250514",
            system_prompt = "You are a senior support supervisor..."
        }
        Supervisor.turn({inject = input.issue})
        return {resolution = Supervisor.output}
    end
}

-- Main entry point
main = procedure "main" {
    input = {
        user_message = {type = "string", required = true}
    },
    output = {
        response = {type = "string"},
        resolved = {type = "boolean"}
    },
    state = {
        category = {type = "string"},
        escalated = {type = "boolean", default = false}
    },
    run = function()
        -- Model for ML classification
        IntentClassifier = model "intent_classifier" {
            type = "bert",
            path = "models/intent.pt",
            labels = {"billing", "technical", "general"}
        }

        -- Agents for LLM-powered conversation
        BillingAgent = agent "billing" {
            model = "claude-sonnet-4-20250514",
            system_prompt = "You handle billing inquiries..."
        }

        TechnicalAgent = agent "technical" {
            model = "claude-sonnet-4-20250514",
            system_prompt = "You handle technical support..."
        }

        -- Route based on ML classification
        state.category = IntentClassifier.predict(input.user_message)

        if state.category == "billing" then
            BillingAgent.turn()
            response = BillingAgent.output
        elseif state.category == "technical" then
            TechnicalAgent.turn()
            response = TechnicalAgent.output
        end

        state.escalated = Human.approve({message = "Escalate to supervisor?"})

        if state.escalated then
            result = handle_escalation({  -- Call sub-procedure (checkpointed)
                issue = input.user_message,
                history = BillingAgent.messages
            })
            response = result.resolution
        end

        return {response = response, resolved = true}
    end
}
```

### Automatic Checkpointing

Every agent turn, model prediction, human interaction, and tool call automatically creates a checkpoint. No explicit step definitions required for common cases:

```lua
state.intent = Classifier.predict(text)  -- Checkpoint 1 (ML inference)
Worker.turn()                            -- Checkpoint 2 (LLM call)
Human.approve({...})                     -- Checkpoint 3 (suspends until response)
Publisher.turn()                         -- Checkpoint 4 (LLM call)
```

### Checkpoint-and-Replay Execution Model

Inspired by AWS Lambda Durable Functions, Tactus uses a replay-based execution model:

1. Procedure runs from the beginning
2. Completed operations return cached results (skip execution)
3. First uncompleted operation executes normally
4. State and execution log persist after each checkpoint

This model enables:
- Zero-compute suspension while waiting for human input
- Automatic resumption from exact checkpoint
- Portable execution across different environments

## Procedure Definitions

### Anatomy of a Procedure

A procedure is a callable unit with defined input, output, state, and a run function:

```lua
my_procedure = procedure "my_procedure" {
    input = {
        -- What the caller provides (read-only)
        document = {type = "string", required = true},
        max_length = {type = "number", default = 500}
    },
    output = {
        -- What the procedure returns
        summary = {type = "string", required = true},
        word_count = {type = "number"}
    },
    state = {
        -- Working data that persists across checkpoints
        chunks = {type = "array", default = {}},
        current_index = {type = "number", default = 0}
    },
    run = function()
        -- Procedure logic here
        -- Access input.document, input.max_length
        -- Read/write state.chunks, state.current_index
        -- Return output at the end
        return {summary = "...", word_count = 42}
    end
}
```

### Input, Output, and State

| Schema | Purpose | Access | Lifetime |
|--------|---------|--------|----------|
| `input` | Caller-provided data | Read-only | Set at invocation |
| `output` | Procedure result | Via `return` | Set at completion |
| `state` | Working data | Read/write | Persists across checkpoints |

### Entry Point Convention

The runtime looks for a `main` procedure as the entry point:

```lua
-- helpers.tactus.lua

helper_a = procedure "helper_a" {
    input = {...},
    output = {...},
    run = function() ... end
}

helper_b = procedure "helper_b" {
    input = {...},
    output = {...},
    run = function() ... end
}

main = procedure "main" {
    input = {...},
    output = {...},
    state = {...},
    run = function()
        -- Entry point - calls helpers as needed
        result_a = helper_a({...})
        result_b = helper_b({...})
        return {...}
    end
}
```

### Sub-Procedure Calls are Checkpointed

Calling a sub-procedure is a durable operation. The entire sub-procedure result is cached:

```lua
main = procedure "main" {
    input = {document = {type = "string"}},
    output = {result = {type = "string"}},
    state = {summaries = {type = "array", default = {}}},
    run = function()
        chunks = split(input.document, 1000)
        
        for i, chunk in ipairs(chunks) do
            result = summarize_chunk({chunk = chunk})  -- Checkpoint!
            state.summaries[i] = result.summary
        end
        
        return {result = join(state.summaries)}
    end
}
```

Execution log:
```
Position 0: summarize_chunk({chunk: "..."}) → {summary: "..."}
Position 1: summarize_chunk({chunk: "..."}) → {summary: "..."}
Position 2: summarize_chunk({chunk: "..."}) → {summary: "..."}
```

On replay, completed sub-procedure calls return cached results without re-execution.

### Script Mode (Simple Cases)

For simple scripts, you can omit the `main` wrapper. Top-level code becomes the entry point:

**Simplest (no schemas):**
```lua
Worker = agent "worker" { model = "claude-sonnet-4-20250514" }
Worker.turn({inject = input.text})
return {result = Worker.output}
```

**With schemas:**
```lua
input {text = {type = "string", required = true}}
output {result = {type = "string"}}

Worker = agent "worker" { model = "claude-sonnet-4-20250514" }
Worker.turn({inject = input.text})
return {result = Worker.output}
```

**Hybrid (sub-procedures with top-level main):**
```lua
input {document = {type = "string"}}
output {result = {type = "string"}}

summarize_chunk = procedure "summarize_chunk" {
    input = {chunk = {type = "string"}},
    output = {summary = {type = "string"}},
    run = function()
        Summarizer = agent "summarizer" { model = "claude-sonnet-4-20250514" }
        Summarizer.turn({inject = input.chunk})
        return {summary = Summarizer.output}
    end
}

-- Top-level code acts as main
chunks = split(input.document, 1000)
for i, chunk in ipairs(chunks) do
    state.results[i] = summarize_chunk({chunk = chunk}).summary
end
return {result = join(state.results)}
```

### Procedure Metadata

Optional metadata for documentation and tooling:

```lua
main = procedure "main" {
    description = "Processes customer support inquiries",
    version = "1.2.0",
    author = "support-team@example.com",
    tags = {"support", "classification"},
    
    input = {...},
    output = {...},
    state = {...},
    run = function() ... end
}
```

## Checkpoint Mechanics

### Execution Log Structure

```python
{
    "procedure_id": "run_abc123",
    "execution_log": [
        {
            "position": 0,
            "name": "intent_classifier_predict",
            "type": "model_predict",
            "result": "billing",
            "timestamp": "2025-01-15T10:30:00Z",
            "duration_ms": 45
        },
        {
            "position": 1,
            "name": "billing_turn",
            "type": "agent_turn",
            "result": {"output": "...", "messages": [...]},
            "timestamp": "2025-01-15T10:30:00Z",
            "duration_ms": 1523
        },
        {
            "position": 2,
            "name": "escalation_approval",
            "type": "hitl_approval",
            "status": "completed",
            "request": {"message": "Escalate to supervisor?"},
            "result": true,
            "timestamp": "2025-01-15T10:30:02Z"
        },
        {
            "position": 3,
            "name": "handle_escalation",
            "type": "procedure_call",
            "input": {"issue": "...", "history": [...]},
            "result": {"resolution": "..."},
            "timestamp": "2025-01-15T10:30:05Z",
            "duration_ms": 3200
        }
    ],
    "state": {
        "category": "billing",
        "escalated": true
    },
    "status": "completed",
    "replay_index": 4
}
```

### Replay Behavior

On resume, the procedure replays from the beginning:

```
Position 0: intent_classifier_predict → Skip, return cached "billing"
Position 1: billing_turn              → Skip, return cached response
Position 2: escalation_approval       → Skip, return cached true
Position 3: handle_escalation         → Skip, return cached {resolution: "..."}
Position 4: (end)                     → Procedure complete
```

### Position-Based Checkpointing

Checkpoints are keyed by execution position, not name. This handles loops naturally:

```lua
for i, item in ipairs(items) do
    Worker.turn({inject = "Process: " .. item})  -- Same code, different positions
end
```

Execution log:
```
Position 0: worker_turn (item 1) → result
Position 1: worker_turn (item 2) → result
Position 2: worker_turn (item 3) → result
```

## State Management

### The `state` Table

The `state` table persists across checkpoints. Local variables do not:

```lua
-- ✅ Works: state persists
state.request_id = math.random(1000)
Worker.turn()
if state.request_id > 500 then  -- request_id available on replay
    Publisher.turn()
end

-- ❌ Breaks: local var lost on replay
local request_id = math.random(1000)
Worker.turn()  -- Checkpoint here
if request_id > 500 then  -- request_id undefined on replay!
    Publisher.turn()
end
```

### State Schema

Procedures declare state schema for validation and documentation:

```lua
procedure "order_fulfillment" {
    state = {
        order_id = {type = "string", required = true},
        status = {type = "string", default = "pending", 
                  enum = {"pending", "processing", "shipped", "delivered"}},
        shipping_address = {type = "table"},
        attempts = {type = "number", default = 0}
    }
}
```

Runtime validates mutations against schema, catching errors early.

## Explicit Steps (Optional)

For complex logic or semantic organization, explicit steps are available:

```lua
step("research", function()
    state.phase = "researching"
    Researcher.turn()
    state.findings = Researcher.output
end)

step("approval", function()
    state.approved = Human.approve({
        message = "Approve findings?",
        context = state.findings
    })
end)

if state.approved then
    step("publish", function()
        Publisher.turn({inject = state.findings})
    end)
end
```

Steps provide:
- Semantic naming for logs and debugging
- Logical grouping of related operations
- Potential retry boundaries
- Better checkpoint names (`research.agent_1` vs `auto_agent_1`)

### Steps and Auto-Checkpointing Compose

Operations inside steps still auto-checkpoint independently:

```lua
step("mixed_operations", function()
    call_api()          -- Part of step checkpoint
    Worker.turn()       -- Its OWN checkpoint (auto)
    call_another_api()  -- Part of step checkpoint
end)
```

Each `Worker.turn()` creates its own checkpoint regardless of step boundaries.

## Explicit Checkpoint Primitive

For cases where you want to checkpoint state without an agent/HITL operation, use the `checkpoint()` primitive:

```lua
state.expensive_result = really_expensive_computation()
checkpoint()  -- Explicitly save state here

risky_external_call()  -- If this fails, we don't redo the expensive computation
```

### When to Use Explicit Checkpoints

**After expensive pure computations:**
```lua
state.embeddings = compute_embeddings(large_document)  -- CPU-intensive
state.clusters = cluster_embeddings(state.embeddings)  -- Also expensive
checkpoint()  -- Save before proceeding

Worker.turn({inject = state.clusters})
```

**Before risky operations:**
```lua
state.prepared_data = prepare_for_upload(raw_data)
checkpoint()  -- Save preparation work

external_api.upload(state.prepared_data)  -- Might fail/timeout
```

**At logical boundaries in long computations:**
```lua
for i, batch in ipairs(batches) do
    state.results[i] = process_batch(batch)
    
    if i % 10 == 0 then
        checkpoint()  -- Periodic save every 10 batches
    end
end
```

### What Explicit Checkpoints Do NOT Do

Explicit checkpoints do **not** create a suspend point. They simply persist current state to storage. The procedure continues executing immediately.

For suspend points (waiting for external input), use HITL primitives like `Human.approve()` or `Human.input()`.

## Agent and Model Primitives

Tactus distinguishes between two types of inference primitives:

### Agents (LLM-powered, conversational)

Agents wrap Pydantic AI and support conversation history, tools, and structured output:

```lua
Researcher = agent "researcher" {
    model = "claude-sonnet-4-20250514",
    system_prompt = "You are a research assistant...",
    tools = {web_search, read_file},
    output_type = ResearchReport
}

Reviewer = agent "reviewer" {
    model = "gpt-4o",
    system_prompt = "You review research reports for accuracy..."
}
```

**Agent methods:**

```lua
Researcher.turn()                          -- Take a conversation turn
Researcher.turn({inject = "Research X"})   -- Inject user message
state.report = Researcher.output           -- Get last output
state.history = Researcher.messages        -- Access conversation history
```

### Models (Generic ML inference)

Models wrap any ML inference - classifiers, extractors, embeddings, etc:

```lua
IntentClassifier = model "intent_classifier" {
    type = "bert",
    path = "models/intent.pt",
    labels = {"billing", "technical", "general"}
}

QuoteExtractor = model "quote_extractor" {
    type = "http",
    endpoint = "http://ml-service:8000/extract",
    timeout = 30
}

Embedder = model "embedder" {
    type = "sentence_transformers",
    model_name = "all-MiniLM-L6-v2"
}
```

**Model methods:**

```lua
state.intent = IntentClassifier.predict(user_message)
state.quotes = QuoteExtractor.predict({text = document, min_length = 10})
state.embedding = Embedder.predict(text)
```

### Supported Model Types

| Type | Description | Example Use Case |
|------|-------------|------------------|
| `bert` | HuggingFace transformers | Text classification, NER |
| `sklearn` | Scikit-learn models | Naive Bayes, SVM, Random Forest |
| `pytorch` | Custom PyTorch models | Any `.pt` file |
| `onnx` | ONNX runtime | Cross-platform inference |
| `sentence_transformers` | Sentence embeddings | Semantic search, clustering |
| `http` | REST endpoint | External ML services |
| `sagemaker` | AWS SageMaker endpoint | Production ML |

### Both Auto-Checkpoint

Regardless of type, all inference operations auto-checkpoint:

```lua
Researcher.turn()                           -- Checkpoint (LLM call)
state.intent = IntentClassifier.predict(x)  -- Checkpoint (BERT inference)
state.quotes = QuoteExtractor.predict(doc)  -- Checkpoint (HTTP call)
```

On replay, cached results are returned without re-running inference.

## Human-in-the-Loop (HITL)

### Approval Pattern

```lua
state.approved = Human.approve({
    message = "Deploy to production?",
    context = {
        changes = state.pending_changes,
        risk_level = state.risk_assessment
    },
    timeout = "24h",
    default_on_timeout = false
})

if state.approved then
    Deployer.turn()
end
```

### Input Pattern

```lua
state.user_feedback = Human.input({
    prompt = "Please provide additional context:",
    input_type = "text",
    required = true
})

Analyst.turn({inject = state.user_feedback})
```

### HITL Execution Flow

1. Procedure reaches `Human.approve()` or `Human.input()`
2. Checkpoint created with `status: "waiting"`
3. Procedure suspends (zero compute cost)
4. External system receives callback URL/message ID
5. Human responds via API/UI
6. Callback triggers procedure resume
7. Replay runs, returns cached human response at checkpoint
8. Execution continues past HITL call

## Storage Backend Abstraction

### Protocol Definition

```python
from typing import Protocol

class StorageBackend(Protocol):
    async def save_checkpoint(self, procedure_id: str, data: dict) -> None:
        """Save checkpoint data for a procedure run."""
        ...
    
    async def load_checkpoint(self, procedure_id: str) -> dict | None:
        """Load checkpoint data. Returns None if not found."""
        ...
    
    async def delete_checkpoint(self, procedure_id: str) -> None:
        """Delete checkpoint data after successful completion."""
        ...
    
    async def list_checkpoints(self, 
                               status: str | None = None,
                               prefix: str | None = None) -> list[str]:
        """List procedure IDs matching criteria."""
        ...
```

### Implementations

| Environment | Implementation | Notes |
|-------------|----------------|-------|
| Local dev | `MemoryStorage` | Fast, no persistence |
| Local dev | `FileStorage` | JSON files, easy debugging |
| Local dev | `SQLiteStorage` | Single-file database |
| Production | `PostgresStorage` | Relational, ACID |
| Production | `DynamoDBStorage` | AWS serverless |
| Production | `CosmosDBStorage` | Azure serverless |
| Production | `FirestoreStorage` | GCP serverless |
| AWS Lambda | `LambdaDurableStorage` | Native integration |

### Portability

Same Tactus code runs everywhere—only storage configuration changes:

```python
# Local development
runtime = TactusRuntime(storage=FileStorage("./checkpoints"))

# Production AWS
runtime = TactusRuntime(storage=DynamoDBStorage(table="tactus-checkpoints"))

# Same procedure works in both
await runtime.execute("customer_support.tactus.lua", context)
```

## Determinism Requirements

### The Problem

Code outside checkpointed operations can break replay:

```lua
-- Non-deterministic: different value on each replay
local timestamp = os.time()
Worker.turn()
Log.info("Started at: " .. timestamp)  -- Different each replay!
```

### Multi-Layer Protection

**1. Parser Linting (Static Analysis)**

Detects at parse time:
- Non-deterministic functions outside checkpoints (`math.random`, `os.time`)
- State mutations outside checkpoints
- Variables used across checkpoint boundaries

```
Warning: os.time() called outside checkpoint at line 5
  Suggestion: Store result in state before checkpoint
  
Warning: Local variable 'timestamp' used after checkpoint at line 7
  Suggestion: Use state.timestamp instead
```

**2. Runtime Detection**

Instrument non-deterministic functions to warn when called outside checkpoints:

```python
def instrumented_random():
    if not context.inside_checkpoint:
        logger.warning("math.random called outside checkpoint - may break replay")
    return random.random()
```

**3. Strict Mode**

Development flag that throws errors on potential determinism violations:

```python
runtime = TactusRuntime(
    storage=storage,
    strict_determinism=True  # Errors instead of warnings
)
```

**4. Determinism Testing**

Automated test that runs procedure twice and verifies identical execution logs:

```python
async def test_determinism(procedure_path: str):
    run1 = await runtime.execute(procedure_path, context)
    run2 = await runtime.execute(procedure_path, context)
    
    assert run1.execution_log == run2.execution_log, \
        "Non-deterministic execution detected"
```

## Runtime Architecture

### Execution Context

```python
@dataclass
class ExecutionContext:
    procedure_id: str
    execution_log: list[CheckpointEntry]
    replay_index: int
    state: dict
    deps: dict
    storage: StorageBackend
    
    def checkpoint(self, name: str, operation_type: str, fn: Callable) -> Any:
        """Universal checkpoint mechanism."""
        
        # Replay mode: return cached result
        if self.replay_index < len(self.execution_log):
            cached = self.execution_log[self.replay_index]
            self.replay_index += 1
            return cached["result"]
        
        # Execute mode: run and checkpoint
        result = fn()
        
        self.execution_log.append({
            "position": self.replay_index,
            "name": name,
            "type": operation_type,
            "result": result,
            "timestamp": datetime.utcnow().isoformat()
        })
        self.replay_index += 1
        
        self._save_checkpoint()
        return result
    
    def _save_checkpoint(self):
        self.storage.save_checkpoint(self.procedure_id, {
            "execution_log": self.execution_log,
            "state": self.state,
            "replay_index": self.replay_index,
            "status": self._current_status()
        })
```

### Agent Primitive (Auto-Checkpoint)

```python
class AgentPrimitive:
    def __init__(self, agent_name: str, config: dict, context: ExecutionContext):
        self.agent_name = agent_name
        self.config = config
        self.context = context
        self.pydantic_agent = self._create_pydantic_agent(config)
        self.messages: list = []
        self.output: Any = None
    
    def turn(self, options: dict | None = None) -> None:
        checkpoint_name = f"{self.agent_name}_turn_{self.context.next_id()}"
        
        result = self.context.checkpoint(
            name=checkpoint_name,
            operation_type="agent_turn",
            fn=lambda: self._execute_turn(options)
        )
        
        self.output = result["output"]
        self.messages = result["messages"]
    
    def _execute_turn(self, options: dict | None) -> dict:
        # Actual agent execution via Pydantic AI
        inject = options.get("inject") if options else None
        result = self.pydantic_agent.run_sync(
            inject or "",
            message_history=self.messages
        )
        return {
            "output": result.output,
            "messages": self.messages + result.new_messages()
        }
```

### Model Primitive (Auto-Checkpoint)

```python
class ModelPrimitive:
    def __init__(self, model_name: str, config: dict, context: ExecutionContext):
        self.model_name = model_name
        self.config = config
        self.context = context
        self.inference_backend = self._create_backend(config)
    
    def predict(self, input_data: Any) -> Any:
        checkpoint_name = f"{self.model_name}_predict_{self.context.next_id()}"
        
        return self.context.checkpoint(
            name=checkpoint_name,
            operation_type="model_predict",
            fn=lambda: self._execute_predict(input_data)
        )
    
    def _execute_predict(self, input_data: Any) -> Any:
        model_type = self.config.get("type")
        
        if model_type == "bert":
            return self._predict_transformers(input_data)
        elif model_type == "sklearn":
            return self._predict_sklearn(input_data)
        elif model_type == "http":
            return self._predict_http(input_data)
        elif model_type == "sagemaker":
            return self._predict_sagemaker(input_data)
        else:
            raise ValueError(f"Unknown model type: {model_type}")
    
    def _predict_http(self, input_data: Any) -> Any:
        response = requests.post(
            self.config["endpoint"],
            json=input_data,
            timeout=self.config.get("timeout", 30)
        )
        response.raise_for_status()
        return response.json()
```

### Procedure Callable (Auto-Checkpoint)

When a procedure is defined, it returns a callable that auto-checkpoints:

```python
class ProcedureCallable:
    def __init__(self, name: str, config: dict, run_fn: Callable, context: ExecutionContext):
        self.name = name
        self.input_schema = config.get("input", {})
        self.output_schema = config.get("output", {})
        self.state_schema = config.get("state", {})
        self.run_fn = run_fn
        self.context = context
    
    def __call__(self, input_data: dict) -> dict:
        checkpoint_name = f"{self.name}_{self.context.next_id()}"
        
        return self.context.checkpoint(
            name=checkpoint_name,
            operation_type="procedure_call",
            fn=lambda: self._execute(input_data)
        )
    
    def _execute(self, input_data: dict) -> dict:
        # Validate input against schema
        validated_input = self._validate_input(input_data)
        
        # Create nested execution context for sub-procedure
        nested_context = ExecutionContext(
            procedure_id=f"{self.context.procedure_id}/{self.name}",
            execution_log=[],
            replay_index=0,
            state=self._initialize_state(),
            deps=self.context.deps,
            storage=self.context.storage
        )
        
        # Inject input and run
        nested_context.input = validated_input
        result = self.run_fn(nested_context)
        
        # Validate output against schema
        return self._validate_output(result)
```

### Human Primitive (Auto-Checkpoint + Suspend)

```python
class HumanPrimitive:
    def __init__(self, context: ExecutionContext):
        self.context = context
    
    def approve(self, request: dict) -> bool:
        checkpoint_name = f"hitl_approve_{self.context.next_id()}"
        
        # Check if we have a cached response
        if self.context.replay_index < len(self.context.execution_log):
            cached = self.context.execution_log[self.context.replay_index]
            if cached.get("status") == "completed":
                self.context.replay_index += 1
                return cached["result"]
        
        # No cached response - create waiting checkpoint and suspend
        self.context.execution_log.append({
            "position": self.context.replay_index,
            "name": checkpoint_name,
            "type": "hitl_approval",
            "status": "waiting",
            "request": request,
            "timestamp": datetime.utcnow().isoformat()
        })
        self.context._save_checkpoint()
        
        raise SuspendExecution(
            checkpoint_name=checkpoint_name,
            request=request
        )
```

### Explicit Checkpoint Primitive

```python
def checkpoint_primitive(context: ExecutionContext) -> None:
    """
    Explicitly save current state without creating an operation entry.
    Used after expensive computations or before risky operations.
    """
    checkpoint_name = f"explicit_{context.next_id()}"
    
    # During replay, just advance past this checkpoint
    if context.replay_index < len(context.execution_log):
        cached = context.execution_log[context.replay_index]
        if cached.get("type") == "explicit_checkpoint":
            context.replay_index += 1
            return
    
    # Record the explicit checkpoint
    context.execution_log.append({
        "position": context.replay_index,
        "name": checkpoint_name,
        "type": "explicit_checkpoint",
        "state_snapshot": copy.deepcopy(context.state),
        "timestamp": datetime.utcnow().isoformat()
    })
    context.replay_index += 1
    context._save_checkpoint()
```

This is exposed to Lua as simply `checkpoint()`.

## Invocation API

### Starting Fresh

```python
result = await runtime.execute(
    procedure="customer_support.tactus.lua",
    input={"user_message": "I need help with my bill"},
    procedure_id="run_abc123"  # Optional, auto-generated if omitted
)

# Typed output from procedure
print(result.output)  # {"response": "...", "resolved": true}
print(result.status)  # "completed"
```

### Resuming from Checkpoint

```python
# After human responds to HITL request
result = await runtime.resume(
    procedure_id="run_abc123",
    hitl_response={"approved": True}  # Injected into waiting checkpoint
)
```

### Checking Status

```python
status = await runtime.get_status("run_abc123")
# Returns: "running" | "waiting_for_human" | "completed" | "failed"

checkpoint = await runtime.get_checkpoint("run_abc123")
# Returns full checkpoint data for inspection
```

### Input Validation

```python
# If procedure defines: input = {user_message = {type = "string", required = true}}

# This succeeds
result = await runtime.execute(
    procedure="customer_support.tactus.lua",
    input={"user_message": "Help!"}
)

# This fails with validation error
result = await runtime.execute(
    procedure="customer_support.tactus.lua",
    input={}  # Missing required field
)
# Raises: InputValidationError("Missing required field: user_message")
```

## Comparison with Alternatives

### vs. Pydantic Graph

| Aspect | Pydantic Graph | Tactus |
|--------|---------------|--------|
| Language | Python classes | Lua DSL |
| Control flow | Return next node | Normal if/else |
| Checkpoint granularity | Per-node | Per-operation (auto) |
| Node definition | Required (dataclasses) | Optional (steps) |
| Type safety | Full Python typing | Runtime validation |
| Learning curve | Graph paradigm | Natural imperative |

### vs. LangGraph

| Aspect | LangGraph | Tactus |
|--------|-----------|--------|
| Persistence | State + position snapshot | Execution log replay |
| Resume mechanism | Jump to checkpoint | Replay from start |
| Graph definition | Required | Not required |
| Checkpoint control | Explicit | Automatic |

### vs. AWS Lambda Durable Functions

| Aspect | Lambda Durable | Tactus |
|--------|---------------|--------|
| Execution model | Same (replay) | Same (replay) |
| Language | JavaScript/Python | Lua |
| Environment | AWS only | Portable |
| Step definition | `context.step()` | Auto or explicit |

## Implementation Phases

### Phase 1: Core Runtime
- Execution context with checkpoint/replay
- State management and persistence
- Basic storage backends (Memory, File)

### Phase 2: Agent Integration
- Agent primitive with auto-checkpointing
- Pydantic AI integration
- Conversation history management
- Tool call checkpointing

### Phase 3: Model Integration
- Model primitive with auto-checkpointing
- HTTP endpoint backend
- HuggingFace transformers backend
- Scikit-learn backend

### Phase 4: HITL
- Human primitives (approve, input)
- Suspend/resume mechanism
- Callback URL generation

### Phase 5: Production Storage
- PostgresStorage implementation
- DynamoDBStorage implementation
- Connection pooling and reliability

### Phase 6: Developer Experience
- Parser-based linting for determinism
- Mermaid diagram generation
- Debugging tools and visualization

### Phase 7: Advanced Features
- Parallel step execution
- Retry policies per step
- Timeout handling
- Workflow composition

## Open Questions

1. **Timeout handling**: How should long-running HITL requests be handled? Default response? Escalation?

2. **Versioning**: What happens when procedure code changes between checkpoint and resume?

3. **Large state**: Should we support external state references for large data (S3 pointers, etc.)?

4. **Observability**: Integration with Logfire/OpenTelemetry for tracing?

5. **Error recovery**: Retry policies, dead letter queues, manual intervention?