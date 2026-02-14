# Model Primitive

NOTE: This document is retained for historical context, but the canonical,
copy/pasteable reference is now:

- `docs/model-primitive.md` (humans + AI assistants)
- `llms.txt` (machine-ingestible guidance)

The Tactus `Model` primitive is a first-class, declarative way to define and use
predictive models inside procedures. A `Model` is **stateless** and **cacheable**:
it takes input and produces output, without multi-turn behavior. If you need
conversation, tools, or memory, use an `Agent` instead.

This doc focuses on **how it works today** and how to use it.

---

## When to Use Model vs Agent

- **Model**: deterministic or probabilistic inference (classification, extraction,
  embeddings, regression). One call in, one output out.
- **Agent**: multi-turn reasoning, tool use, planning, conversation.

---

## Quick Start

### 1) Declare a model

```lua
Model "sentiment" {
  type = "registry",
  name = "sentiment",
  version = "latest",
  input = { text = "string" },
  output = { label = "string", confidence = "float" }
}
```

### 2) Use it in a procedure

```lua
Procedure {
  input = { text = field.string{required = true} },
  output = { label = field.string{required = true} },
  function(input)
    local classifier = Model("sentiment")
    local result = classifier({text = input.text})
    local output = result.output or result
    return { label = output.label }
  end
}
```

---

## Training in the Same File

Training configuration lives inside the Model under `training`.

```lua
Model "imdb_nb" {
  type = "registry",
  name = "imdb_nb",
  version = "latest",
  input = { text = "string" },
  output = { label = "string", confidence = "float" },
  training = {
    data = {
      source = "hf",
      name = "imdb",
      train = "train",
      test = "test",
      text_field = "text",
      label_field = "label"
    },
    candidates = {
      {
        name = "nb-tfidf",
        trainer = "naive_bayes",
        hyperparameters = {
          alpha = 1.0,
          max_features = 50000,
          ngram_min = 1,
          ngram_max = 2
        }
      }
    }
  }
}
```

### Train

```bash
tactus train my-file.tac --model imdb_nb
```

### Evaluate

```bash
tactus models evaluate my-file.tac --model imdb_nb
```

Evaluation uses the `training.data.test` split and a **registered** model version.

---

## Registry Behavior

Training registers artifacts in the registry and applies tags:

- `latest`
- `candidate/<candidate_name>`

Advanced: you can apply additional tags with `tactus models promote`.
This is optional; most examples use `latest` and `candidate/<name>`.

---

## Mocking Models in Specs

You can mock model outputs with a `Mocks {}` block and run tests with `--mock`.
Mocks support static, temporal, and conditional responses.

```lua
Mocks {
  imdb_nb = {
    conditional = {
      {when = {text = "Great movie"}, returns = {label = "positive", confidence = 0.92}},
      {when = {text = "Bad movie"}, returns = {label = "negative", confidence = 0.87}}
    }
  }
}
```

Run mocked specs:

```bash
tactus test examples/47-model-naive-bayes-train.tac --mock
```

Run against a real trained model:

```bash
tactus test examples/47-model-naive-bayes-train.tac
```

---

## Supported Backends

Runtime model types:

- `http`
- `pytorch`
- `sklearn`
- `hf_sequence_classifier`
- `llm`
- `registry`
- `ensemble`
- `ab_test` / `traffic_split`

See `tactus/primitives/model.py` and `tactus/backends/` for details.

---

## Examples

- `examples/47-model-naive-bayes-train.tac` - single-file training + runtime + specs
- `examples/49-model-compare-train.tac` - multiple candidates (Naive Bayes vs HF sequence classifier)

---

## Notes

- Training requires a `training` block. Missing it is a hard error.
- Evaluation runs on the **registered** model, not a fresh training run.
- Model declarations are best kept at top level for static analysis.
