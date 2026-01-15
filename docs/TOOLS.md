# Tools in Tactus

This guide explains the major tool types in Tactus, where they run, and how to keep secrets out of sandboxed runs.

## Table of Contents

1. [Overview](#overview)
2. [Trust Zones](#trust-zones)
3. [Brokered Host Tools](#brokered-host-tools)
4. [Quick Start](#quick-start)
5. [Three Approaches](#three-approaches)
6. [Parameter Specifications](#parameter-specifications)
7. [Tool Implementation Patterns](#tool-implementation-patterns)
8. [Error Handling](#error-handling)
9. [Tool Call Tracking](#tool-call-tracking)
10. [Advanced Examples](#advanced-examples)
11. [Comparison with Plugin Tools](#comparison-with-plugin-tools)
12. [Best Practices](#best-practices)

## Overview

Tactus supports several tool types:

- **Built-in Tactus tools** (shipped with Tactus): e.g. `tactus.tools.done`
- **Lua function tools** (defined inside `.tac`): simple, fast, co-located with the workflow
- **Python plugin tools** (loaded from `tool_paths`): run Python code from your repo without MCP
- **MCP tools** (Model Context Protocol): tools provided by external stdio servers
- **Brokered host tools** (Phase 1B): privileged “host-side” tools executed by the broker and invoked from the sandbox via `Host.call(...)`

Lua function tools support three ways to define tools:

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

## Trust Zones

Tactus aims to keep the **runtime container** (when using `--sandbox`) both:

- **Networkless** by default (`--network none`)
- **Secretless** (no long-lived API keys in the container env, mounts, or request payload)

That means not all “tools” are equal: different tool types run in different trust zones.

At a high level:

- **Lua tools** run inside the runtime (and therefore inside the sandbox container when `--sandbox` is enabled).
- **MCP servers** run as subprocesses of the runtime (so they share the runtime’s trust zone unless explicitly isolated).
- **Brokered host tools** run on the trusted host-side broker and can hold secrets without exposing them to the sandbox.

For the broader architecture (including future isolated tool runners), see `planning/BROKER_AND_TOOL_RUNNERS.md`.

## Brokered Host Tools

Brokered host tools are allowlisted operations executed by the **host-side broker** and invoked from the runtime via the `Host` primitive.

This is the core mechanism for “remote tools with secrets” (e.g., a Tab search API key) while keeping the sandbox container secretless.

### Running the Example

Run the example:

```bash
tactus sandbox rebuild --force
tactus run examples/66-host-tools-via-broker.tac --sandbox --verbose
```

Call a host tool from Lua:

```lua
local result = Host.call("host.ping", {value = 1})
```

Or wrap it as a normal `Tool` using a broker tool source:

```lua
host_ping = Tool { use = "broker.host.ping" } -- calls broker allowlisted tool: host.ping

local result = host_ping({value = 1})
```

### Default Allowlist (Phase 1B)

The default broker allowlist intentionally starts small:

- `host.ping`
- `host.echo`

To add real host tools, extend the broker’s allowlist (see `tactus/broker/server.py:HostToolRegistry`).

## Quick Start

Here's the simplest example:

```lua
-- Import completion tool
done = tactus.done

-- Define a custom tool
greet = Tool {
    description = "Greet someone by name",
    input = {
        name = field.string{required = true, description = "Person's name"}
    },
    function(args)
        return "Hello, " .. args.name .. "!"
    end
}

-- Use tools in an agent
assistant = Agent {
    provider = "openai",
    system_prompt = "You are a friendly assistant",
    tools = {greet, done}  -- Variable references, not strings
}

Procedure {
    function(input)
        assistant({message = "Greet Alice"})
        return {result = "done"}
    end
}
```

That's it! The agent can now call your Lua functions as tools.

## Three Approaches

### 1. Individual Tool Declarations

**Best for**: Single-purpose tools, reusable utilities

Define tools at the top level of your `.tac` file:

```lua
done = tactus.done

calculate_tip = Tool {
    description = "Calculate tip amount for a bill",
    input = {
        bill_amount = field.number{required = true},
        tip_percentage = field.number{required = true}
    },
    function(args)
        local tip = args.bill_amount * (args.tip_percentage / 100)
        return string.format("Tip: $%.2f", tip)
    end
}

assistant = Agent {
    provider = "openai",
    tools = {calculate_tip, done}  -- Variable references
}
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
done = tactus.done

math_tools = Toolset {
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
}

calculator = Agent {
    provider = "openai",
    tools = {math_tools, done}  -- Variable references
}
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
done = tactus.done

text_processor = Agent {
    provider = "openai",
    system_prompt = "You process text",
    inline_tools = {
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
    tools = {done}
}
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
example = Tool {
    description = "Example tool",
    input = {
        -- Required parameter
        name = field.string{
            description = "User's name",
            required = true  -- Must be provided
        },
        -- Optional parameter with default
        greeting = field.string{
            description = "Greeting message",
            default = "Hello"
        },
        -- Optional without default (nil if not provided)
        suffix = field.string{
            description = "Optional suffix"
        }
    },
    function(args)
        local msg = (args.greeting or "Hello") .. ", " .. args.name
        if args.suffix then
            msg = msg .. " " .. args.suffix
        end
        return msg
    end
}
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
compound_interest = Tool {
    description = "Calculate compound interest",
    input = {
        principal = field.number{description = "Initial amount", required = true},
        rate = field.number{description = "Annual interest rate (%)", required = true},
        years = field.integer{description = "Number of years", required = true}
    },
    function(args)
        local amount = args.principal * (1 + args.rate / 100) ^ args.years
        local interest = amount - args.principal
        return string.format("Final: $%.2f (Interest: $%.2f)", amount, interest)
    end
}
```

### Pattern 2: String Manipulation

```lua
format_phone = Tool {
    description = "Format phone number",
    input = {
        number = field.string{description = "Phone number digits", required = true}
    },
    function(args)
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
    end
}
```

### Pattern 3: Data Aggregation

```lua
analyze_list = Tool {
    description = "Analyze a list of numbers",
    input = {
        numbers = field.array{description = "List of numbers", required = true}
    },
    function(args)
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
    end
}
```

### Pattern 4: Conditional Logic

```lua
categorize_age = Tool {
    description = "Categorize person by age",
    input = {
        age = field.integer{description = "Person's age", required = true}
    },
    function(args)
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
    end
}
```

## Error Handling

### Validation in Tool Functions

```lua
divide = Tool {
    description = "Divide two numbers",
    input = {
        numerator = field.number{required = true},
        denominator = field.number{required = true}
    },
    function(args)
        -- Validate before processing
        if args.denominator == 0 then
            return "Error: Division by zero"
        end

        if type(args.numerator) ~= "number" or type(args.denominator) ~= "number" then
            return "Error: Both arguments must be numbers"
        end

        local result = args.numerator / args.denominator
        return string.format("%.4f", result)
    end
}
```

### Error Propagation

Errors in Lua tools are caught and logged, then re-raised as `RuntimeError`:

```lua
risky_operation = Tool {
    description = "Operation that might fail",
    input = {
        value = field.number{required = true}
    },
    function(args)
        -- This error will be caught, logged, and re-raised
        if args.value < 0 then
            error("Value must be positive")
        end

        return tostring(args.value * 2)
    end
}
```

The agent will receive an error message and can decide how to handle it (retry, report to user, etc.).

## Tool Call Tracking

### Checking if a Tool Was Called

```lua
Procedure {
    function(input)
        assistant({message = "Calculate something"})

        if calculate_tip.called() then
            Log.info("Tip calculator was used")
        end

        if done.called() then
            Log.info("Agent finished")
        end

        return {result = "done"}
    end
}
```

### Getting Tool Call Results

```lua
Procedure {
    function(input)
        assistant({message = "Add 5 and 3"})

        if add.called() then
            local call = add.last_call()
            Log.info("Arguments: " .. tostring(call.args.a) .. ", " .. tostring(call.args.b))
            Log.info("Result: " .. call.result)
        end

        return {result = "done"}
    end
}
```

### Tracking Multiple Calls

```lua
Procedure {
    function(input)
        assistant({message = "Do several calculations"})

        local tools_used = {}
        if add.called() then table.insert(tools_used, "add") end
        if subtract.called() then table.insert(tools_used, "subtract") end
        if multiply.called() then table.insert(tools_used, "multiply") end
        if divide.called() then table.insert(tools_used, "divide") end

        if #tools_used > 0 then
            Log.info("Tools used: " .. table.concat(tools_used, ", "))
        end

        return {result = "done"}
    end
}
```

## Advanced Examples

### Example 1: State Management Tool

```lua
-- Tool that accesses procedure state
update_counter = Tool {
    description = "Increment a counter",
    input = {
        amount = field.integer{description = "Amount to add", default = 1}
    },
    function(args)
        -- Access state directly
        local current = state.counter or 0
        local new_value = current + args.amount
        state.counter = new_value
        return string.format("Counter: %d -> %d", current, new_value)
    end
}
```

### Example 2: Multi-Step Calculation

```lua
done = tactus.done

financial_tools = Toolset {
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
}
```

### Example 3: Text Processing Pipeline

```lua
done = tactus.done

content_editor = Agent {
    provider = "openai",
    system_prompt = "You are a content editing assistant",
    inline_tools = {
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
    tools = {done}
}
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
- Can't safely hold secrets (use brokered host tools instead)

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

### Brokered Host Tools (via Host.call)

**Pros:**
- Secrets stay out of the sandbox container
- Can perform network calls without giving the runtime network access
- Centralized allowlist and auditing point (the broker)

**Cons:**
- Requires a broker transport (`--sandbox` uses broker by default)
- Must be explicitly allowlisted (deny-by-default)
- Privileged by design; treat host tools as trusted code

**Best for:**
- Remote API tools that require API keys
- “Host-integrated” capabilities (e.g., talking to a local index, keychain, or daemon)
- Anything that must be kept out of the untrusted runtime container

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

Use **Brokered Host Tools** when:
- A tool needs secrets but the runtime container must remain secretless
- The runtime container must remain networkless (`--network none`)
- You want a narrow, allowlisted capability surface area

## Best Practices

### 1. Clear Descriptions

```lua
-- Bad: Vague description
process = Tool {
    description = "Process data",
    ...
}

-- Good: Specific description
calculate_compound_interest = Tool {
    description = "Calculate compound interest given principal, annual rate, and time period",
    ...
}
```

### 2. Validate Inputs

```lua
calculate_bmi = Tool {
    description = "Calculate Body Mass Index",
    input = {
        weight_kg = field.number{description = "Weight in kilograms", required = true},
        height_m = field.number{description = "Height in meters", required = true}
    },
    function(args)
        -- Validate inputs
        if args.weight_kg <= 0 or args.height_m <= 0 then
            return "Error: Weight and height must be positive"
        end

        local bmi = args.weight_kg / (args.height_m ^ 2)
        return string.format("BMI: %.1f", bmi)
    end
}
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
-- Single reusable tool -> Tool {}
celsius_to_fahrenheit = Tool {...}

-- Related tools -> Toolset {}
temperature_tools = Toolset {
    type = "lua",
    tools = {...}
}

-- Agent-specific -> inline in Agent
temp_converter = Agent {
    inline_tools = {...},
    tools = {done}
}
```

### 5. Keep Tools Focused

```lua
-- Bad: Tool does too much
do_everything = Tool {
    description = "Calculate, format, and analyze data",
    ...
}

-- Good: Separate concerns
calculate_total = Tool {...}
format_currency = Tool {...}
analyze_trend = Tool {...}
```

### 6. Document Complex Logic

```lua
amortization_schedule = Tool {
    description = "Generate loan amortization schedule",
    input = {...},
    function(args)
        -- Calculate monthly payment using standard mortgage formula:
        -- M = P * [r(1+r)^n] / [(1+r)^n - 1]
        -- where P = principal, r = monthly rate, n = number of payments

        local monthly_rate = args.annual_rate / 100 / 12
        local num_payments = args.years * 12

        -- ... implementation
    end
}
```

### 7. Handle Edge Cases

```lua
calculate_percentage = Tool {
    description = "Calculate percentage",
    input = {
        part = field.number{required = true},
        whole = field.number{required = true}
    },
    function(args)
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
    end
}
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
