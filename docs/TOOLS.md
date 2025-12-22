# Defining Tools with Lua Functions

This guide explains how to define tools as Lua functions within Tactus procedures, giving agents the ability to perform custom operations without requiring external Python plugins or MCP servers.

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Three Approaches](#three-approaches)
4. [Parameter Specifications](#parameter-specifications)
5. [Tool Implementation Patterns](#tool-implementation-patterns)
6. [Error Handling](#error-handling)
7. [Tool Call Tracking](#tool-call-tracking)
8. [Advanced Examples](#advanced-examples)
9. [Comparison with Plugin Tools](#comparison-with-plugin-tools)
10. [Best Practices](#best-practices)

## Overview

Tactus supports three ways to define tools as Lua functions:

1. **Individual `tool()` declarations** - Define single tools globally
2. **`toolset()` with `type="lua"`** - Group multiple related tools
3. **Inline agent tools** - Define tools directly in agent configuration

All three approaches are powered by Pydantic AI's function toolset feature and integrate seamlessly with the existing toolset system.

### Why Lua Function Tools?

- **Zero setup**: No external files or servers required
- **Co-located**: Tool definitions live next to their usage
- **Type-safe**: Parameter validation through Pydantic models
- **Tracked**: Full integration with `Tool.called()` and `Tool.last_call()`
- **Fast**: Minimal overhead for simple operations

## Quick Start

Here's the simplest example:

```lua
-- Define a tool
tool("greet", {
    description = "Greet someone by name",
    parameters = {
        name = {type = "string", description = "Person's name", required = true}
    }
}, function(args)
    return "Hello, " .. args.name .. "!"
end)

-- Use it in an agent
agent("assistant", {
    provider = "openai",
    system_prompt = "You are a friendly assistant",
    toolsets = {"greet", "done"}
})

procedure(function()
    Assistant.turn("Greet Alice")
    return {result = "done"}
end)
```

That's it! The agent can now call your Lua function as a tool.

## Three Approaches

### 1. Individual tool() Declarations

**Best for**: Single-purpose tools, reusable utilities

Define tools at the top level of your `.tac` file:

```lua
tool("calculate_tip", {
    description = "Calculate tip amount for a bill",
    parameters = {
        bill_amount = {type = "number", required = true},
        tip_percentage = {type = "number", required = true}
    }
}, function(args)
    local tip = args.bill_amount * (args.tip_percentage / 100)
    return string.format("Tip: $%.2f", tip)
end)

agent("assistant", {
    provider = "openai",
    toolsets = {"calculate_tip", "done"}  -- Reference by name
})
```

**Pros:**
- Simple and explicit
- Each tool gets its own toolset
- Easy to reference by name
- Reusable across agents

**Cons:**
- Can get verbose with many tools
- Each tool is a separate toolset entry

### 2. Toolset with type="lua"

**Best for**: Groups of related tools, domain-specific functions

Group multiple tools into a named toolset:

```lua
toolset("math_tools", {
    type = "lua",
    tools = {
        {
            name = "add",
            description = "Add two numbers",
            parameters = {
                a = {type = "number", required = true},
                b = {type = "number", required = true}
            },
            handler = function(args)
                return tostring(args.a + args.b)
            end
        },
        {
            name = "multiply",
            description = "Multiply two numbers",
            parameters = {
                a = {type = "number", required = true},
                b = {type = "number", required = true}
            },
            handler = function(args)
                return tostring(args.a * args.b)
            end
        }
    }
})

agent("calculator", {
    provider = "openai",
    toolsets = {"math_tools", "done"}  -- All tools in one reference
})
```

**Pros:**
- Organizes related tools together
- Single toolset reference
- Clean namespace management
- Good for domain-specific operations

**Cons:**
- More nested structure
- All-or-nothing (can't select individual tools from the set)

### 3. Inline Agent Tools

**Best for**: Agent-specific tools, one-off utilities

Define tools directly in the agent configuration:

```lua
agent("text_processor", {
    provider = "openai",
    system_prompt = "You process text",
    tools = {
        {
            name = "uppercase",
            description = "Convert to uppercase",
            parameters = {
                text = {type = "string", required = true}
            },
            handler = function(args)
                return string.upper(args.text)
            end
        },
        {
            name = "lowercase",
            description = "Convert to lowercase",
            parameters = {
                text = {type = "string", required = true}
            },
            handler = function(args)
                return string.lower(args.text)
            end
        }
    },
    toolsets = {"done"}  -- Can mix inline tools with toolsets
})
```

**Pros:**
- Co-located with agent definition
- No global namespace pollution
- Perfect for agent-specific logic
- Automatically prefixed with agent name

**Cons:**
- Not reusable by other agents
- Can make agent config large
- Tool names are prefixed (`agent_name_tool_name`)

## Parameter Specifications

### Supported Types

Map Lua type names to Python types for validation:

| Lua Type | Python Type | Example |
|----------|-------------|---------|
| `"string"` | `str` | `"hello"` |
| `"number"` | `float` | `42.5` |
| `"integer"` | `int` | `42` |
| `"boolean"` | `bool` | `true/false` |
| `"table"` | `dict` | `{key = "value"}` |
| `"array"` | `list` | `{1, 2, 3}` |

### Required vs Optional Parameters

```lua
tool("example", {
    description = "Example tool",
    parameters = {
        -- Required parameter
        name = {
            type = "string",
            description = "User's name",
            required = true  -- Must be provided
        },
        -- Optional parameter with default
        greeting = {
            type = "string",
            description = "Greeting message",
            required = false,
            default = "Hello"
        },
        -- Optional without default (nil if not provided)
        suffix = {
            type = "string",
            description = "Optional suffix",
            required = false
        }
    }
}, function(args)
    local msg = (args.greeting or "Hello") .. ", " .. args.name
    if args.suffix then
        msg = msg .. " " .. args.suffix
    end
    return msg
end)
```

### Parameter Descriptions

Descriptions help the LLM understand when and how to use parameters:

```lua
parameters = {
    amount = {
        type = "number",
        description = "Amount in dollars (positive number)",  -- Be specific!
        required = true
    },
    currency = {
        type = "string",
        description = "Currency code (e.g., USD, EUR, GBP)",  -- Provide examples
        required = false,
        default = "USD"
    }
}
```

## Tool Implementation Patterns

### Pattern 1: Simple Calculations

```lua
tool("compound_interest", {
    description = "Calculate compound interest",
    parameters = {
        principal = {type = "number", description = "Initial amount", required = true},
        rate = {type = "number", description = "Annual interest rate (%)", required = true},
        years = {type = "integer", description = "Number of years", required = true}
    }
}, function(args)
    local amount = args.principal * (1 + args.rate / 100) ^ args.years
    local interest = amount - args.principal
    return string.format("Final: $%.2f (Interest: $%.2f)", amount, interest)
end)
```

### Pattern 2: String Manipulation

```lua
tool("format_phone", {
    description = "Format phone number",
    parameters = {
        number = {type = "string", description = "Phone number digits", required = true}
    }
}, function(args)
    -- Remove non-digits
    local digits = string.gsub(args.number, "%D", "")

    -- Format as (XXX) XXX-XXXX
    if string.len(digits) == 10 then
        return string.format("(%s) %s-%s",
            string.sub(digits, 1, 3),
            string.sub(digits, 4, 6),
            string.sub(digits, 7, 10))
    end

    return "Invalid phone number"
end)
```

### Pattern 3: Data Aggregation

```lua
tool("analyze_list", {
    description = "Analyze a list of numbers",
    parameters = {
        numbers = {type = "array", description = "List of numbers", required = true}
    }
}, function(args)
    local sum = 0
    local min = math.huge
    local max = -math.huge
    local count = 0

    for _, num in ipairs(args.numbers) do
        sum = sum + num
        min = math.min(min, num)
        max = math.max(max, num)
        count = count + 1
    end

    local avg = sum / count

    return string.format(
        "Count: %d, Sum: %g, Avg: %g, Min: %g, Max: %g",
        count, sum, avg, min, max
    )
end)
```

### Pattern 4: Conditional Logic

```lua
tool("categorize_age", {
    description = "Categorize person by age",
    parameters = {
        age = {type = "integer", description = "Person's age", required = true}
    }
}, function(args)
    if args.age < 0 then
        return "Invalid age"
    elseif args.age < 13 then
        return "Child"
    elseif args.age < 20 then
        return "Teenager"
    elseif args.age < 65 then
        return "Adult"
    else
        return "Senior"
    end
end)
```

## Error Handling

### Validation in Tool Functions

```lua
tool("divide", {
    description = "Divide two numbers",
    parameters = {
        numerator = {type = "number", required = true},
        denominator = {type = "number", required = true}
    }
}, function(args)
    -- Validate before processing
    if args.denominator == 0 then
        return "Error: Division by zero"
    end

    if type(args.numerator) ~= "number" or type(args.denominator) ~= "number" then
        return "Error: Both arguments must be numbers"
    end

    local result = args.numerator / args.denominator
    return string.format("%.4f", result)
end)
```

### Error Propagation

Errors in Lua tools are caught and logged, then re-raised as `RuntimeError`:

```lua
tool("risky_operation", {
    description = "Operation that might fail",
    parameters = {
        value = {type = "number", required = true}
    }
}, function(args)
    -- This error will be caught, logged, and re-raised
    if args.value < 0 then
        error("Value must be positive")
    end

    return tostring(args.value * 2)
end)
```

The agent will receive an error message and can decide how to handle it (retry, report to user, etc.).

## Tool Call Tracking

### Checking if a Tool Was Called

```lua
procedure(function()
    Assistant.turn("Calculate something")

    if Tool.called("calculate_tip") then
        Log.info("Tip calculator was used")
    end

    if Tool.called("done") then
        Log.info("Agent finished")
    end

    return {result = "done"}
end)
```

### Getting Tool Call Results

```lua
procedure(function()
    Assistant.turn("Add 5 and 3")

    if Tool.called("add") then
        local call = Tool.last_call("add")
        Log.info("Arguments: " .. tostring(call.args.a) .. ", " .. tostring(call.args.b))
        Log.info("Result: " .. call.result)
    end

    return {result = "done"}
end)
```

### Tracking Multiple Calls

```lua
procedure(function()
    Assistant.turn("Do several calculations")

    local tools_used = {}
    for _, tool_name in ipairs({"add", "subtract", "multiply", "divide"}) do
        if Tool.called(tool_name) then
            table.insert(tools_used, tool_name)
        end
    end

    if #tools_used > 0 then
        Log.info("Tools used: " .. table.concat(tools_used, ", "))
    end

    return {result = "done"}
end)
```

## Advanced Examples

### Example 1: State Management Tool

```lua
-- Tool that accesses procedure state
tool("update_counter", {
    description = "Increment a counter",
    parameters = {
        amount = {type = "integer", description = "Amount to add", required = false, default = 1}
    }
}, function(args)
    -- Access State primitive from tool
    local current = State.get("counter") or 0
    local new_value = current + args.amount
    State.set("counter", new_value)
    return string.format("Counter: %d -> %d", current, new_value)
end)
```

### Example 2: Multi-Step Calculation

```lua
toolset("financial_tools", {
    type = "lua",
    tools = {
        {
            name = "calculate_loan_payment",
            description = "Calculate monthly loan payment",
            parameters = {
                principal = {type = "number", description = "Loan amount", required = true},
                annual_rate = {type = "number", description = "Annual interest rate (%)", required = true},
                years = {type = "integer", description = "Loan term in years", required = true}
            },
            handler = function(args)
                local monthly_rate = args.annual_rate / 100 / 12
                local num_payments = args.years * 12

                local payment
                if monthly_rate == 0 then
                    payment = args.principal / num_payments
                else
                    payment = args.principal * (monthly_rate * (1 + monthly_rate) ^ num_payments) /
                              ((1 + monthly_rate) ^ num_payments - 1)
                end

                local total_paid = payment * num_payments
                local total_interest = total_paid - args.principal

                return string.format(
                    "Monthly Payment: $%.2f\nTotal Paid: $%.2f\nTotal Interest: $%.2f",
                    payment, total_paid, total_interest
                )
            end
        },
        {
            name = "calculate_affordability",
            description = "Calculate maximum affordable home price",
            parameters = {
                monthly_income = {type = "number", description = "Monthly gross income", required = true},
                monthly_debts = {type = "number", description = "Monthly debt payments", required = true},
                down_payment = {type = "number", description = "Available down payment", required = true},
                interest_rate = {type = "number", description = "Expected interest rate (%)", required = true}
            },
            handler = function(args)
                -- Use 28% of gross income rule
                local max_payment = args.monthly_income * 0.28 - args.monthly_debts

                -- Calculate affordable loan amount
                local monthly_rate = args.interest_rate / 100 / 12
                local num_payments = 30 * 12

                local max_loan
                if monthly_rate == 0 then
                    max_loan = max_payment * num_payments
                else
                    max_loan = max_payment * ((1 + monthly_rate) ^ num_payments - 1) /
                               (monthly_rate * (1 + monthly_rate) ^ num_payments)
                end

                local max_price = max_loan + args.down_payment

                return string.format(
                    "Max Monthly Payment: $%.2f\nMax Loan Amount: $%.2f\nMax Home Price: $%.2f",
                    max_payment, max_loan, max_price
                )
            end
        }
    }
})
```

### Example 3: Text Processing Pipeline

```lua
agent("content_editor", {
    provider = "openai",
    system_prompt = "You are a content editing assistant",
    tools = {
        {
            name = "word_count",
            description = "Count words in text",
            parameters = {
                text = {type = "string", required = true}
            },
            handler = function(args)
                local count = 0
                for _ in string.gmatch(args.text, "%S+") do
                    count = count + 1
                end
                return tostring(count)
            end
        },
        {
            name = "reading_time",
            description = "Estimate reading time",
            parameters = {
                word_count = {type = "integer", description = "Number of words", required = true},
                wpm = {type = "integer", description = "Words per minute", required = false, default = 200}
            },
            handler = function(args)
                local minutes = math.ceil(args.word_count / args.wpm)
                return string.format("%d min read", minutes)
            end
        },
        {
            name = "extract_sentences",
            description = "Split text into sentences",
            parameters = {
                text = {type = "string", required = true}
            },
            handler = function(args)
                local sentences = {}
                for sentence in string.gmatch(args.text, "[^.!?]+[.!?]") do
                    table.insert(sentences, string.match(sentence, "^%s*(.-)%s*$"))
                end
                return table.concat(sentences, "\n")
            end
        }
    },
    toolsets = {"done"}
})
```

## Comparison with Plugin Tools

### Lua Function Tools

**Pros:**
- Zero setup - defined inline
- Fast for simple operations
- Co-located with usage
- Full Lua language features
- Direct access to State primitive

**Cons:**
- Lua language constraints
- No async operations
- Limited to Lua ecosystem
- Can't call external APIs directly

**Best for:**
- Data transformations
- Calculations
- String manipulation
- Business logic
- State access

### Python Plugin Tools

**Pros:**
- Full Python ecosystem
- Can be async
- External API calls
- Complex libraries
- Type hints in Python

**Cons:**
- Requires external files
- Setup overhead
- Separated from .tac file
- No direct State access

**Best for:**
- External API integration
- Heavy computation
- Using Python libraries
- Shared across projects
- Complex algorithms

### When to Use Which?

Use **Lua Function Tools** when:
- The tool is specific to this procedure
- Logic is simple (< 20 lines)
- You need access to State
- Setup time matters
- The operation is pure logic/math

Use **Plugin Tools** when:
- Tool is reused across procedures
- You need external APIs
- Logic is complex (> 20 lines)
- You need Python libraries
- Async operations required

Use **MCP Tools** when:
- Tool is provided by external service
- You need remote capabilities
- Tool is maintained separately
- Multiple procedures share it

## Best Practices

### 1. Clear Descriptions

```lua
-- Bad: Vague description
tool("process", {
    description = "Process data",
    ...
})

-- Good: Specific description
tool("calculate_compound_interest", {
    description = "Calculate compound interest given principal, annual rate, and time period",
    ...
})
```

### 2. Validate Inputs

```lua
tool("calculate_bmi", {
    description = "Calculate Body Mass Index",
    parameters = {
        weight_kg = {type = "number", description = "Weight in kilograms", required = true},
        height_m = {type = "number", description = "Height in meters", required = true}
    }
}, function(args)
    -- Validate inputs
    if args.weight_kg <= 0 or args.height_m <= 0 then
        return "Error: Weight and height must be positive"
    end

    local bmi = args.weight_kg / (args.height_m ^ 2)
    return string.format("BMI: %.1f", bmi)
end)
```

### 3. Return Meaningful Results

```lua
-- Bad: Unclear result
handler = function(args)
    return tostring(args.a + args.b)
end

-- Good: Clear, formatted result
handler = function(args)
    local result = args.a + args.b
    return string.format("%g + %g = %g", args.a, args.b, result)
end
```

### 4. Use Appropriate Approach

```lua
-- Single reusable tool -> tool()
tool("celsius_to_fahrenheit", ...)

-- Related tools -> toolset()
toolset("temperature_tools", {
    type = "lua",
    tools = {...}
})

-- Agent-specific -> inline
agent("temp_converter", {
    tools = {...}
})
```

### 5. Keep Tools Focused

```lua
-- Bad: Tool does too much
tool("do_everything", {
    description = "Calculate, format, and analyze data",
    ...
})

-- Good: Separate concerns
tool("calculate_total", {...})
tool("format_currency", {...})
tool("analyze_trend", {...})
```

### 6. Document Complex Logic

```lua
tool("amortization_schedule", {
    description = "Generate loan amortization schedule",
    parameters = {...}
}, function(args)
    -- Calculate monthly payment using standard mortgage formula:
    -- M = P * [r(1+r)^n] / [(1+r)^n - 1]
    -- where P = principal, r = monthly rate, n = number of payments

    local monthly_rate = args.annual_rate / 100 / 12
    local num_payments = args.years * 12

    -- ... implementation
end)
```

### 7. Handle Edge Cases

```lua
tool("calculate_percentage", {
    description = "Calculate percentage",
    parameters = {
        part = {type = "number", required = true},
        whole = {type = "number", required = true}
    }
}, function(args)
    -- Handle division by zero
    if args.whole == 0 then
        return "Error: Cannot calculate percentage of zero"
    end

    -- Handle negative numbers
    if args.whole < 0 or args.part < 0 then
        return "Error: Values must be positive"
    end

    local percentage = (args.part / args.whole) * 100
    return string.format("%.2f%%", percentage)
end)
```

## Summary

Lua function tools provide a powerful, flexible way to extend agent capabilities directly within your `.tac` files:

- **Three approaches**: Choose based on reusability and scope
- **Type-safe**: Parameters validated through Pydantic
- **Tracked**: Full integration with tool call tracking
- **Simple**: Zero external dependencies
- **Fast**: Minimal overhead

For more examples, see:
- `examples/18-feature-lua-tools-individual.tac`
- `examples/18-feature-lua-tools-toolset.tac`
- `examples/18-feature-lua-tools-inline.tac`

For formal syntax, see `SPECIFICATION.md`.
