# Tactus Standard Library

The Tactus standard library provides reusable modules for building AI agents, classification, extraction, and retrieval workflows.

## Architecture

The stdlib is **Tactus-first**: all modules are implemented in `.tac` files. Python is used only as a lower-level escape hatch when a Python library is genuinely needed (e.g., rapidfuzz for string similarity, openpyxl for Excel I/O).

1. **BDD specs define behavior** - Each module has `.spec.tac` files as the contract
2. **Tactus code is primary** - All class hierarchies and logic live in `.tac` files
3. **Python is a helper** - Only for functionality requiring Python libraries

## Structure

```
tactus/stdlib/
├── tac/tactus/                  # PRIMARY: Tactus module implementations
│   ├── classify/                # Classification (LLM + fuzzy matching)
│   │   ├── init.tac             # Module entry point + Classify factory
│   │   ├── base.tac             # BaseClassifier + class helper
│   │   ├── llm.tac              # LLM-based classifier (now uses Model primitive)
│   │   ├── naive_bayes.tac       # Registry-backed Naive Bayes classifier
│   │   └── fuzzy.tac            # Fuzzy classifier (calls Python similarity)
│   ├── models/                  # Model primitive helpers
│   │   ├── init.tac             # Module entry
│   │   ├── llm.tac              # LLM Model wrapper built on Model primitive
│   │   └── naive_bayes.tac       # Naive Bayes model helper (registry-backed)
│   │   └── hf_sequence_classifier.tac   # Hugging Face sequence classifier helper
│   ├── extract/                 # Structured data extraction
│   ├── generate/                # LLM-based generation
│   ├── retrievers/              # Search/retrieval systems
│   ├── corpora/                 # Corpus management
│   ├── tools/                   # Utility tools (log, done)
│   ├── classify.spec.tac        # BDD specs for classify
│   └── extract.spec.tac         # BDD specs for extract
│
├── classify/                    # Python helpers for classify
│   └── similarity.py            # rapidfuzz-backed string similarity
├── io/                          # Python I/O modules (json, csv, file, etc.)
├── biblicus/                    # Python Biblicus bindings
├── core/                        # Shared Python utilities
└── loader.py                    # Python module loader for require()
```

## Available Modules

- `tactus.classify` - LLM, Naive Bayes, and fuzzy string matching classification
- `tactus.models` - Helpers for Model primitive (e.g., `tactus.models.llm`, `tactus.models.naive_bayes`, `tactus.models.hf_sequence_classifier`)
- Ensembles & A/B: Model primitive supports `type = "ensemble"` (vote/average) and `type = "ab_test"` routing with metadata (`arm_index`)
- `tactus.extract` - Structured extraction utilities
- `tactus.generate` - LLM-based generation helpers
- `tactus.retrievers.*` - Search/retrieval systems
- `tactus.io.*` - File I/O helpers (json, csv, tsv, file)
- `biblicus.text` - Biblicus-backed text utilities

## Usage

```lua
-- Via require()
local classify = require("tactus.classify")
local classifier = classify.LLMClassifier:new {
    classes = {"Yes", "No"},
    prompt = "Is this a question?"
}
local result = classifier:classify("How are you?")

-- Via Classify global (convenience)
result = Classify {
    classes = {"Yes", "No"},
    prompt = "Is this a question?",
    input = "How are you?"
}

-- Python helpers loaded as fallback
local json = require("tactus.io.json")
local data = json.read("config.json")

-- Model helper
local models = require("tactus.models")
local sentiment = models.LLMModel{
    name = "sentiment",
    classes = {"positive", "negative", "neutral"},
    prompt = "Classify sentiment",
    model = "openai/gpt-4o-mini",
}
local prediction = sentiment({text = "great!"})

-- Naive Bayes classifier (registry-backed, trained via tactus train)
local nb = classify.NaiveBayesClassifier:new {
    name = "imdb_nb"
}
local nb_result = nb:classify("An excellent movie")

-- Hugging Face sequence classifier helper
local models = require("tactus.models")
local classifier = models.HFSequenceClassifierModel{
    model = "distilbert-base-uncased-finetuned-sst-2-english"
}
local classifier_result = classifier({text = "great movie"})

-- Hugging Face sequence classifier training (full hyperparameter control)
Model "imdb_bert" {
  input = { text = "string" },
  output = { label = "string", confidence = "float" },
  training = {
    data = {
      source = "hf",
      name = "imdb",
      train = "train[:2000]",
      test = "test[:500]",
      text_field = "text",
      label_field = "label"
    },
    candidates = {
      {
        name = "bert-base",
        trainer = "hf_sequence_classifier",
        hyperparameters = {
          model = "distilbert-base-uncased",
          labels = {"negative", "positive"},
          epochs = 1,
          batch_size = 8,
          learning_rate = 2e-5,
          max_length = 256,
          padding = "max_length",
          truncation = true,
          training_args = {
            evaluation_strategy = "epoch",
            logging_steps = 25,
            save_strategy = "no"
          }
        }
      }
    }
  }
}

-- Ensemble / A/B examples (see examples/43-model-ensemble.tac, 44-model-ab-test.tac)
```

## Testing

Run all stdlib specs:
```bash
tactus stdlib test
```

Run specific module specs:
```bash
tactus test tactus/stdlib/tac/tactus/classify.spec.tac
```

## Adding New Modules

1. Create a `.tac` module in `tac/tactus/your-module/`
2. Write a `.spec.tac` with BDD scenarios
3. If Python is needed, add a helper `.py` in `your-module/` with `__tactus_exports__`
4. Ensure `tactus test` passes
