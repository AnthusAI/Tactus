-- Demonstrates Jinja2 templating, locals, opt-in state, and plain mode.

Mocks {
    jinja_agent = {
        conditional_mocks = {
            {
                when = {inject = "Hello Pat from Sea. visits=2"},
                ["return"] = {response = "templated-ok"}
            }
        }
    },
    plain_agent = {
        conditional_mocks = {
            {
                -- Should NOT render the template; expect raw braces
                when = {inject = "Plain literal {{ locals.note }} for {{ input.name }}"},
                ["return"] = {response = "plain-ok"}
            }
        }
    }
}

jinja_agent = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_message = "Use the provided greeting template.",
    message = "Hello {{ input.name }} from {{ locals.region }}. visits={{ state.visits }}",
    template_context = {
        locals = {region = "Sea"},
        state = {"visits"}
    }
}

plain_agent = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_message = "This should remain unchanged: {{ locals.note }}",
    message = "Plain literal {{ locals.note }} for {{ input.name }}",
    template_mode = "plain",
    template_context = {
        locals = {note = "noop"}
    }
}

Procedure {
    input = {
        name = field.string{default = "Pat"}
    },
    output = {
        templated = field.string{required = true},
        plain = field.string{required = true}
    },
    state = {
        visits = field.number{default = 2}
    },
    function(input)
        -- Call the templated agent (mocked)
        local templated = jinja_agent()

        -- Call the plain-mode agent (mocked)
        local plain = plain_agent()

        return {
            templated = templated and templated.response or "missing",
            plain = plain and plain.response or "missing"
        }
    end
}

Specifications([[
Feature: Templating modes
  Scenario: Jinja2 renders and plain mode preserves literals
    Given a Lua DSL file "examples/73-templating-modes.tac"
    When I execute the procedure
    Then the execution should succeed
    And the output should contain field "templated" with value "templated-ok"
    And the output should contain field "plain" with value "plain-ok"
]])
