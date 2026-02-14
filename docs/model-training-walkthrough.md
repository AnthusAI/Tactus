# Train + Evaluate + Run Models (Hands-on Walkthrough)

This walkthrough is for people who want to *play with the Model primitive* and understand how training, the registry, evaluation, mocks, and procedures fit together.

For the short canonical reference, see:

- `docs/model-primitive.md`
- `llms.txt`

## What you will do

1) Run a procedure with **mocked** model outputs (deterministic, CI-safe).
2) Train a real model and register it in the **local registry**.
3) Evaluate the trained model on a test split.
4) Run the same procedure against the **real** trained model.
5) Compare multiple candidates (Naive Bayes vs HF sequence classifier).

## Setup: choose an isolated local registry (recommended)

By default, the local registry writes to `~/.tactus/models`.

For experiments, it's often nicer to isolate the registry:

```bash
export TACTUS_REGISTRY_TYPE=local
export TACTUS_REGISTRY_DIR="$(mktemp -d)"
echo "Using registry dir: $TACTUS_REGISTRY_DIR"
```

## Step 1: Run in mock mode (fast, deterministic)

This tests *your procedure logic* (branching decisions) without requiring any ML dependencies or model artifacts.

```bash
tactus test examples/47-model-naive-bayes-train.tac --mock
```

You should see scenarios that cover:

- positive -> `decision="yes"`
- negative -> `decision="no"`
- low confidence -> `decision="review"`

## Step 2: Install ML dependencies for training

Core Tactus does not install heavy ML libraries by default.

For Naive Bayes training:

```bash
pip install "tactus[ml]"
```

For Hugging Face sequence classifier training:

```bash
pip install "tactus[hf]"
```

## Step 3: Train a real model and register it

Train the model declared inside the file (Option A: `Model.training` lives in the same file):

```bash
tactus train examples/47-model-naive-bayes-train.tac --model imdb_nb
```

Training will:

- load the dataset declared in `Model.training.data`
- train the candidates declared in `Model.training.candidates`
- register a version to the registry under `Model.name`
- apply tags:
  - `latest`
  - `candidate/<candidate_name>`

## Step 4: Inspect what was registered

List versions for the model name:

```bash
tactus models list imdb_nb
```

You should see versions with tags like `latest` and `candidate/nb-tfidf`.

## Step 5: Evaluate the trained model

Evaluate reads:

- the **test split** declared in `Model.training.data.test`
- a **registry-backed** model version/tag

Default is `latest`:

```bash
tactus models evaluate examples/47-model-naive-bayes-train.tac --model imdb_nb
```

Or target a candidate tag explicitly:

```bash
tactus models evaluate examples/47-model-naive-bayes-train.tac --model imdb_nb --candidate nb-tfidf
```

## Step 6: Run the procedure against the real trained model

Once you have trained + registered the model, you can run the same `.tac` file without mocks:

```bash
tactus test examples/47-model-naive-bayes-train.tac
```

This uses `Model("imdb_nb")` at runtime, which resolves the configured version/tag from the registry.

## Step 7: Compare multiple candidates (Naive Bayes vs HF)

Use the comparison example:

```bash
tactus train examples/49-model-compare-train.tac --model imdb_compare
```

Then evaluate each candidate tag:

```bash
tactus models evaluate examples/49-model-compare-train.tac --model imdb_compare --candidate nb-tfidf
tactus models evaluate examples/49-model-compare-train.tac --model imdb_compare --candidate hf-distilbert
```

Notes:

- When you train multiple candidates in one run, `latest` will end up pointing at the last candidate trained.
- For comparisons, prefer `--candidate ...` so you always evaluate the candidate you mean.

## Common troubleshooting

### "datasets not installed"

Install the right extras:

- `pip install "tactus[ml]"` (Naive Bayes)
- `pip install "tactus[hf]"` (HF sequence classifier)

### Wrapper vs raw output

In procedure code, always normalize:

```lua
local out = result.output or result
```

This keeps your procedure stable across different model backends and across mock vs real runs.

### Forcing CPU for HF training

HF Trainer uses GPU automatically when available. To force CPU:

```lua
hyperparameters = {
  model = "distilbert-base-uncased",
  training_args = { no_cuda = true }
}
```

