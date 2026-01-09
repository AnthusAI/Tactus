--[[
Example: JSON File I/O

Demonstrates reading and writing JSON files using File.read/write with Json.encode/decode.
Json.encode/decode work with strings for JSON serialization.

To run:
  tactus run examples/54-json-file-io.tac
]]--

Procedure {
    input = {
    },
    output = {
            users_processed = field.number{required = true},
            active_users = field.number{required = true}
    },
    function(input)

    -- Create complex nested data structure
        local app_config = {
            app_name = "Tactus Example App",
            version = "1.0.0",
            settings = {
                debug = false,
                max_connections = 100,
                timeout_seconds = 30,
                features = {"auth", "logging", "metrics"}
            },
            users = {
                {
                    id = 1,
                    username = "alice",
                    email = "alice@example.com",
                    active = true,
                    roles = {"admin", "user"},
                    metadata = {
                        last_login = "2024-01-15",
                        login_count = 42
                    }
                },
                {
                    id = 2,
                    username = "bob",
                    email = "bob@example.com",
                    active = true,
                    roles = {"user"},
                    metadata = {
                        last_login = "2024-01-14",
                        login_count = 15
                    }
                },
                {
                    id = 3,
                    username = "charlie",
                    email = "charlie@example.com",
                    active = false,
                    roles = {"user"},
                    metadata = {
                        last_login = "2023-12-01",
                        login_count = 3
                    }
                }
            }
        }

        -- Write JSON file using File.write and Json.encode
        local json_str = Json.encode(app_config)
        File.write("app_config.json", json_str)
        Log.info("Created app configuration JSON file")

        -- Read it back using File.read and Json.decode
        local json_content = File.read("app_config.json")
        local loaded_config = Json.decode(json_content)

        -- Process the data
        local active_count = 0
        local total_logins = 0

        for _, user in ipairs(loaded_config.users) do
            if user.active then
                active_count = active_count + 1
            end
            total_logins = total_logins + user.metadata.login_count

            Log.debug("User info", {
                username = user.username,
                active = user.active,
                roles = table.concat(user.roles, ", ")
            })
        end

        -- Create a summary report
        local summary = {
            report_date = os.date(),
            app = {
                name = loaded_config.app_name,
                version = loaded_config.version
            },
            statistics = {
                total_users = #loaded_config.users,
                active_users = active_count,
                inactive_users = #loaded_config.users - active_count,
                total_logins = total_logins,
                average_logins = total_logins / #loaded_config.users
            },
            enabled_features = loaded_config.settings.features
        }

        -- Write summary using File.write
        local summary_json = Json.encode(summary)
        File.write("app_summary.json", summary_json)

        -- Also demonstrate Json.encode/decode for string operations
        local encoded = Json.encode({quick = "test", number = 123})
        Log.info("Encoded JSON string", {json = encoded})

        local decoded = Json.decode(encoded)
        Log.info("Decoded value", {quick = decoded.quick})

        return {
            users_processed = #loaded_config.users,
            active_users = active_count
        }
    end
}

Specifications([[
Feature: JSON File IO
  Read and write complex JSON structures

  Scenario: Process application configuration
    Given the procedure has started
    When the procedure runs
    Then the procedure should complete successfully
    And the output users_processed should be 3
    And the output active_users should be 2
]])
