--[[
Example: Brokered Host Tool Source

Demonstrates wrapping an allowlisted broker host tool as a normal `Tool` and
calling it directly from Lua (no agent required).

To run (requires sandbox/broker):
  tactus sandbox rebuild --force
  tactus run examples/67-host-tool-source.tac --sandbox --verbose
]]--

host_ping = Tool {
    use = "broker.host.ping",
    description = "Ping the broker allowlisted host tool (host.ping)"
}

Procedure {
    output = {
        ok = field.boolean{required = true},
        echo = field.object{required = true},
    },
    function(input)
        local result = host_ping({value = 1})
        return {
            ok = result.ok,
            echo = result.echo,
        }
    end
}

Specification([[
Feature: Brokered Host Tool Source
  Wrap and call an allowlisted broker tool from Lua

  Scenario: Ping succeeds
    Given the procedure has started
    When the procedure runs
    Then the procedure should complete successfully
    And the output ok should be True
]])

