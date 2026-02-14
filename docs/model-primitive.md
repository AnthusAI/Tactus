# Model Primitive (Human + LLM Quick Reference)

This document is the canonical reference for how to *think about* and *use* the Tactus **Model** primitive.

If you are writing docs, examples, or AI assistance prompts, copy from here.

## One-sentence definition

A **Model** is Tactus's stateless prediction interface: you give it a typed input, you get a typed output, and you can train/version/evaluate it over time.

## Model vs Agent

Use a **Model** when you want:

- stateless inference (classification, extraction, scoring)
- crisp input/output contracts
- outputs that drive deterministic control flow
- training + evaluation + versioning

Use an **Agent** when you want:

- multi-turn reasoning and dialogue
- tools + planning loops
- adaptive behavior over time

Rule of thumb:

- Models produce signals.
- Procedures make decisions.
- Agents do open-ended work.

## The canonical runtime call pattern (always use this)

In a `Procedure`, you look up a model by name and call it like a function.

```lua
local m = Model("imdb_nb")
local result = m({text = input.text})
local out = result.output or result  -- unwrap wrapper vs raw output
```

Why `out = result.output or result` matters:

- Some backends return a raw output table.
- Others return a wrapper (e.g., `{ output = {...}, metrics = {...} }`).

This one line keeps procedure code stable across backends and across mock vs real runs.

## Single-file design (Option A): training + runtime live in one Model block

Training config is first-class under `Model.training` (not a separate file or top-level config blob).

```lua
Model "imdb_nb" {
  -- runtime / registry lookup
  type = "registry",
  name = "imdb_nb",
  version = "latest",
  input = { text = "string" },
  output = { label = "string", confidence = "float" },

  -- training
  training = {
    data = { /* dataset config */ },
    candidates = { /* trainer configs */ }
  }
}
```

The registry is the link between training and runtime:

- Training writes artifacts + metadata to the registry under `Model.name`.
- Runtime reads a version/tag from the registry using `Model("name")`.

## CLI: train + evaluate

Train (writes to registry):

```bash
tactus train path/to/file.tac --model imdb_nb
```

Evaluate (reads from registry, scores against `training.data.test`):

```bash
tactus models evaluate path/to/file.tac --model imdb_nb
```

When a file contains multiple models, `--model` is how you select which one to train/evaluate.

## Registry versions/tags

Canonical tags:

- `latest`
- `candidate/<candidate_name>`

These tags make it easy to evaluate/compare training candidates deterministically.

## Dependencies (do not imply heavy deps in core install)

- Core runtime: `pip install tactus`
- Trainable sklearn models (e.g. Naive Bayes): `pip install "tactus[ml]"`
- Hugging Face training (sequence classifier): `pip install "tactus[hf]"`

## GPU control (Hugging Face training)

Hugging Face training will use GPU automatically when available.

To force CPU training, pass through TrainingArguments:

```lua
hyperparameters = {
  model = "distilbert-base-uncased",
  training_args = { no_cuda = true }
}
```

## Testing story (what specs should assert)

Specs should test *your procedure logic*, not model quality.

- In CI: use `Mocks { ... }` so model outputs are deterministic.
- After training: you can run the same procedure/spec without mocks to sanity-check end-to-end behavior.

The example procedure should branch on model output so the spec asserts meaningful behavior (e.g., yes/no/review).

### Model mocking pattern (conditional)

```lua
Mocks {
  imdb_nb = {
    conditional = {
      {when = {text = "Great movie."}, returns = {label = "positive", confidence = 0.91}},
      {when = {text = "Bad movie."}, returns = {label = "negative", confidence = 0.88}},
      {when = {text = "Meh."}, returns = {label = "positive", confidence = 0.40}}
    }
  }
}
```

## Canonical runnable sources (do not drift)

- Main repo:
  - `examples/47-model-naive-bayes-train.tac`
  - `examples/49-model-compare-train.tac`
- Examples repo:
  - `02-classification/04-model-train-imdb-naive-bayes.tac`
  - `02-classification/05-model-train-imdb-hf-sequence-classifier.tac`

## LLM-facing "Do / Don't"

Do:

- Use `local out = result.output or result`.
- Keep training config under `Model.training`.
- Use `Mocks { ... }` for CI-safe specs that assert branching logic.
- Use `tactus train ... --model <name>` when multiple models exist in a file.

Don't:

- Don't invent `Model.predict()` in the DSL (the model is called like a function).
- Don't assume `pip install tactus` installs `datasets` / `transformers` / `torch`.
- Don't treat evaluation as retraining; evaluation reads a registry-backed version and scores it on the declared test set.

