--[[
Example: Host Tools via Broker

Demonstrates calling a tiny allowlisted host tool from inside the
secretless runtime container via the broker.

To run (requires sandbox/broker):
  tactus sandbox rebuild --force
  tactus run examples/66-host-tools-via-broker.tac --sandbox --verbose
]]--

Procedure {
    output = {
        ok = field.boolean{required = true},
        echo = field.object{required = true},
    },
    function(input)
        local result = Host.call("host.ping", {value = 1})
        return {
            ok = result.ok,
            echo = result.echo,
        }
    end
}

Specification([[
Feature: Host Tools via Broker
  Call a broker allowlisted host tool from the runtime container

  Scenario: Ping succeeds
    Given the procedure has started
    When the procedure runs
    Then the procedure should complete successfully
    And the output ok should be True
]])

