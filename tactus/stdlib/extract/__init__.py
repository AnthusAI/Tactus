"""
Tactus Standard Library - Extract Primitive

Provides smart information extraction with built-in retry logic, validation,
and type coercion for extracted fields.

## Quick Start

    -- Simple extraction
    data = Extract {
        fields = {name = "string", age = "number", email = "string"},
        prompt = "Extract customer information from this conversation",
        input = transcript
    }
    -- data.name = "John Smith"
    -- data.age = 34
    -- data.email = "john@example.com"

## Reusable Extractor

Create an extractor once and use it multiple times:

    customer_info = Extract {
        fields = {name = "string", phone = "string", issue = "string"},
        prompt = "Extract customer details and their reported issue"
    }
    data1 = customer_info(transcript1)
    data2 = customer_info(transcript2)

## Configuration Options

| Option       | Type     | Default | Description                          |
|--------------|----------|---------|--------------------------------------|
| fields       | table    | (req)   | Field names and their types          |
| prompt       | string   | (req)   | Extraction instruction               |
| input        | string   | nil     | Input for one-shot extraction        |
| max_retries  | number   | 3       | Max retry attempts on invalid output |
| temperature  | number   | 0.3     | LLM temperature for extraction       |
| model        | string   | nil     | Override default model               |
| strict       | boolean  | true    | Whether all fields are required      |

## Supported Field Types

| Type    | Description                        | Example Value      |
|---------|------------------------------------|--------------------|
| string  | Text value                         | "John Smith"       |
| number  | Numeric value (int or float)       | 34, 3.14           |
| integer | Integer only                       | 34                 |
| boolean | True/false                         | true, false        |
| list    | Array of values                    | {"a", "b", "c"}    |
| object  | Nested object                      | {key = "value"}    |

## Return Value

The Extract primitive returns extracted fields directly for convenience:

| Access     | Type    | Description                              |
|------------|---------|------------------------------------------|
| data.name  | any     | Extracted value for 'name' field         |
| data.age   | any     | Extracted value for 'age' field          |
| data._error| string  | Error message if extraction failed       |

## Retry Logic

When the LLM returns invalid JSON or missing required fields,
Extract automatically retries with conversational feedback:

1. First attempt: Send extraction request
2. If invalid: Send feedback with validation errors
3. Repeat until valid extraction or max_retries exceeded

## Examples

### Customer Information Extraction

    data = Extract {
        fields = {
            name = "string",
            phone = "string",
            email = "string",
            issue = "string"
        },
        prompt = [[
            Extract the customer's contact information and their issue
            from this support call transcript.
        ]],
        input = transcript
    }

### Order Details with Lists

    order = Extract {
        fields = {
            order_id = "string",
            items = "list",
            total = "number",
            priority = "boolean"
        },
        prompt = "Extract order details from the conversation",
        strict = false  -- Allow missing fields
    }
    result = order(conversation)

### Sentiment with Metadata

    analysis = Extract {
        fields = {
            sentiment = "string",
            confidence = "number",
            key_phrases = "list"
        },
        prompt = "Analyze the sentiment and extract key phrases"
    }
"""

from .primitive import ExtractPrimitive, ExtractHandle
from .llm import LLMExtractor
from ..core.models import ExtractorResult

__all__ = [
    "ExtractPrimitive",
    "ExtractHandle",
    "ExtractorResult",
    "LLMExtractor",
]
