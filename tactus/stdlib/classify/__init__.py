"""
Tactus Standard Library - Classify Primitive

Provides smart classification with built-in retry logic, validation,
and confidence extraction.

## Quick Start

    -- Simple binary classification
    result = Classify {
        classes = {"Yes", "No"},
        prompt = "Did the agent greet the customer?",
        input = transcript
    }
    -- result.value = "Yes"
    -- result.confidence = 0.92
    -- result.explanation = "The agent said 'Hello'..."

## Reusable Classifier

Create a classifier once and use it multiple times:

    sentiment = Classify {
        classes = {"positive", "negative", "neutral"},
        prompt = "What is the sentiment of this text?"
    }
    result1 = sentiment(text1)
    result2 = sentiment(text2)

## Configuration Options

| Option          | Type     | Default    | Description                          |
|-----------------|----------|------------|--------------------------------------|
| classes         | table    | (required) | Valid classification values          |
| prompt          | string   | (required) | Classification instruction           |
| input           | string   | nil        | Input for one-shot classification    |
| max_retries     | number   | 3          | Max retry attempts on invalid output |
| temperature     | number   | 0.3        | LLM temperature for classification   |
| model           | string   | nil        | Override default model               |
| confidence_mode | string   | "heuristic"| "heuristic" or "none"               |

## Return Value

The Classify primitive returns a result with:

| Field       | Type    | Description                              |
|-------------|---------|------------------------------------------|
| value       | string  | The classification (e.g., "Yes", "No")   |
| confidence  | number  | Confidence score (0.0 - 1.0) or nil      |
| explanation | string  | LLM's reasoning for the classification   |
| retry_count | number  | Number of retries needed                 |
| error       | string  | Error message if classification failed   |

## Retry Logic

When the LLM returns an invalid classification (not in the `classes` list),
Classify automatically retries with conversational feedback:

1. First attempt: Send classification request
2. If invalid: Send feedback message with valid options
3. Repeat until valid classification or max_retries exceeded

This mimics the LangGraphScore retry pattern where the LLM sees its
previous mistake and can self-correct.

## Confidence Extraction

In "heuristic" mode (default), confidence is extracted from response text:

- High (0.95): "definitely", "certainly", "clearly", "absolutely"
- Medium-high (0.80): "likely", "probably", "appears to be"
- Low (0.50): "possibly", "might be", "uncertain"
- Default (0.75): When no indicators found

Set `confidence_mode = "none"` to disable confidence extraction.

## Examples

### Binary Classification with NA

    result = Classify {
        classes = {"Yes", "No", "NA"},
        prompt = "Did the agent provide the required information?",
        input = transcript
    }

### Multi-class with Custom Temperature

    urgency = Classify {
        classes = {"critical", "high", "medium", "low"},
        prompt = "What is the urgency level of this support ticket?",
        temperature = 0.1,  -- More deterministic
        max_retries = 5     -- More attempts for complex classification
    }
    result = urgency(ticket_text)

### Sentiment Analysis

    sentiment = Classify {
        classes = {"positive", "negative", "neutral", "mixed"},
        prompt = [[
            Analyze the overall sentiment of the customer feedback.
            Consider both explicit statements and implicit tone.
        ]],
    }

    for _, review in ipairs(reviews) do
        local result = sentiment(review.text)
        Log.info("Review sentiment: " .. result.value)
    end

### Fuzzy String Matching

For string similarity matching (finding the best match from a list):

    -- Match school names with variations
    local FuzzyClassifier = require("tactus.stdlib.classify.fuzzy")

    local school_matcher = FuzzyClassifier {
        classes = {
            "United Education Institute",
            "Abilene Christian University",
            "Arizona School of Integrative Studies"
        },
        threshold = 0.75,
        algorithm = "token_set_ratio"  -- Handles reordered tokens
    }

    local result = school_matcher("Institute Education United Dallas")
    -- result.value = "United Education Institute"
    -- result.matched_text = "United Education Institute"
    -- result.confidence = 0.82

Available algorithms:
- `ratio`: Character-level similarity (default, best for exact matches)
- `token_set_ratio`: Tokenizes and compares unique words (handles reordering)
- `token_sort_ratio`: Sorts tokens before comparing (handles reordering)
- `partial_ratio`: Best substring match (good for partial text)

Binary mode (Yes/No matching):

    local matcher = FuzzyClassifier {
        expected = "Customer Service",
        threshold = 0.8,
        algorithm = "token_set_ratio"
    }

    local result = matcher("Service for Customers")
    -- result.value = "Yes" (matched)
    -- result.matched_text = "Customer Service" (what it matched against)
"""

from .primitive import ClassifyPrimitive, ClassifyHandle
from .llm import LLMClassifier
from .fuzzy import FuzzyMatchClassifier, FuzzyClassifier
from ..core.models import ClassifierResult

__all__ = [
    "ClassifyPrimitive",
    "ClassifyHandle",
    "ClassifierResult",
    "LLMClassifier",
    "FuzzyMatchClassifier",
    "FuzzyClassifier",
]
