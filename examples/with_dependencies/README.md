# Dependency Injection Examples

This directory contains examples demonstrating Tactus's dependency injection feature.

## Examples

### simple_http_test.tac

Minimal example proving that HTTP client dependencies are properly initialized.

**Run it:**
```bash
# Run the procedure
tactus run simple_http_test.tac --param city=Seattle

# Run BDD tests
tactus test simple_http_test.tac
```

**What it demonstrates:**
- Declaring an HTTP client dependency
- Runtime initialization of the dependency
- BDD testing that verifies initialization

### time_lookup.tac

More complete example using worldtimeapi.org (a free API).

**Run it:**
```bash
# Run the procedure
tactus run time_lookup.tac --param timezone=America/New_York

# Run with mocked dependencies (fast)
tactus test time_lookup.tac --mocked --param timezone=America/New_York

# Run with real API (integration test)
tactus test time_lookup.tac --integration --param timezone=America/New_York
```

**What it demonstrates:**
- HTTP client dependency with real API
- Testing with mocked responses
- Testing with real API calls
- BDD specs with mock configuration

## Key Concepts

### Declaring Dependencies

```lua
main = procedure("main", {
    dependencies = {
        my_api = {
            type = "http_client",
            base_url = "https://api.example.com",
            headers = {
                ["Authorization"] = env.API_KEY
            },
            timeout = 30.0
        }
    }
}, function()
    -- Dependencies are automatically created and injected
    Worker.turn()
end)
```

### Testing with Mocks

Configure mocks in Gherkin steps:

```gherkin
Feature: API Integration
  Scenario: Successful API call
    Given the my_api returns '{"status": "success"}'
    When the Worker agent takes turn
    Then the my_api should have been called
```

Run tests:
```bash
# Mocked (fast, no real API calls)
tactus test procedure.tac --mocked

# Integration (real API calls)
tactus test procedure.tac --integration
```

## Supported Resource Types

- **http_client** - HTTP client for API calls
  - Backed by `httpx.AsyncClient`
  - Configuration: base_url, headers, timeout

- **postgres** - PostgreSQL connection pool
  - Backed by `asyncpg`
  - Configuration: connection_string, pool_size

- **redis** - Redis client
  - Backed by `redis.asyncio`
  - Configuration: url

## Benefits

1. **Lifecycle Management** - Resources created on start, cleaned up on exit
2. **Connection Pooling** - Reuse connections across tool calls
3. **Easy Testing** - Mock dependencies for fast unit tests
4. **Integration Testing** - Test with real services when needed
5. **Configuration** - Centralized dependency configuration

## Next Steps

See `SPECIFICATION.md` section on Dependencies for complete documentation.
