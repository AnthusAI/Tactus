-- Example: MCP Server Toolset Identification by Server Name
-- Demonstrates proper identification of MCP toolsets by server name

-- Import completion tool from standard library
local done = require("tactus.tools.done")

-- Define toolsets that reference specific MCP servers
-- Note: These require actual MCP servers to be configured in .tac.yml
Toolset "filesystem_tools" {
    use = "mcp.filesystem"  -- Reference filesystem MCP server
}

Toolset "search_tools" {
    use = "mcp.brave-search"  -- Reference brave-search MCP server
}

-- Agent that uses MCP toolsets by server name
researcher = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[You are a research assistant with access to filesystem and search tools.

Available MCP toolsets:
- Filesystem tools (prefixed with filesystem_)
- Search tools (prefixed with brave-search_)

Use these tools to help with research tasks.
When done, call the done tool.]],

    tools = {"filesystem_tools", "search_tools"},
    tools = {"filesystem_tools", "search_tools", done},
}

-- Alternative: Direct reference to MCP server in agent
file_manager = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[You are a file management assistant.

Use filesystem tools to manage files.
When done, call the done tool.]],

    -- Directly reference MCP server (registered by server name)
    tools = {"filesystem"},
    tools = {"filesystem", done},
}

-- Main procedure

Procedure {
    input = {
            task = field.string{
                default = "list files",
                description = "Task to perform: 'list files' or 'search web'"
            }
    },
    output = {
            result = field.string{required = true, description = "Task result"},
            mcp_tools_used = field.array{description = "List of MCP tools used"},
            completed = field.boolean{required = true, description = "Whether task completed"}
    },
    function(input)

    Log.info("Starting MCP toolset identification demo", {task = input.task})

            -- Choose agent based on task
            local selected_agent
            local message = ""

            if input.task == "list files" then
                selected_agent = file_manager
                message = "Please list the files in the current directory."
            elseif input.task == "search web" then
                selected_agent = researcher
                message = "Please search for 'Lua programming language' and summarize what you find."
            else
                selected_agent = researcher
                message = input.task
            end

            -- Run agent with limit
            local max_turns = 3
            local turn_count = 0
            local result

            repeat
                if turn_count == 0 then
                    result = selected_agent({message = message})
                else
                    result = selected_agent()
                end
                turn_count = turn_count + 1
            until done.called() or turn_count >= max_turns

            -- Track which MCP tools were used
            local mcp_tools = {}

            -- Check for filesystem tools
            local fs_tools = {"filesystem_list_directory", "filesystem_read_file", "filesystem_write_file"}
            for _, tool_name in ipairs(fs_tools) do
                if Tool.called(tool_name) then
                    table.insert(mcp_tools, tool_name)
                end
            end

            -- Check for search tools
            local search_tools = {"brave-search_search"}
            for _, tool_name in ipairs(search_tools) do
                if Tool.called(tool_name) then
                    table.insert(mcp_tools, tool_name)
                end
            end

            -- Get result
            local answer = "Task not completed"
            local completed = false

            if done.called() then
                completed = true
                local call = done.last_call()
                if call and call.args then
                    local ok, reason = pcall(function() return call.args["reason"] end)
                    if ok and reason then
                        answer = reason
                    end
                end
            elseif result and result.message then
                answer = result.message
            end

            Log.info("Task result", {
                completed = completed,
                mcp_tools_used = #mcp_tools,
                result = answer
            })

            return {
                result = answer,
                mcp_tools_used = mcp_tools,
                completed = completed
            }

    -- BDD Specifications
    end
}

Specification([[
Feature: MCP Server Toolset Identification
  Demonstrate proper identification of MCP toolsets by server name

  Scenario: Use filesystem MCP server by name
    Given the procedure has started
    And the input task is "list files"
    And the message is "Please list the files in the current directory."
    And the agent "file_manager" responds with "Here are the files."
    And the agent "file_manager" calls tool "filesystem_list_directory" with args {"path": "."}
    And the agent "file_manager" calls tool "done" with args {"reason": "Here are the files."}
    When the procedure runs
    Then the output completed should be true
    And the filesystem_list_directory tool should be called

  Scenario: Use search MCP server by name
    Given the procedure has started
    And the input task is "search web"
    And the message is "Please search for 'Lua programming language' and summarize what you find."
    And the agent "researcher" responds with "Lua is a lightweight language."
    And the agent "researcher" calls tool "brave-search_search" with args {"query": "Lua programming language"}
    And the agent "researcher" calls tool "done" with args {"reason": "Lua is a lightweight language."}
    When the procedure runs
    Then the output completed should be true
    And the brave-search_search tool should be called
]])

-- Note: This example requires MCP servers to be configured in .tac.yml:
-- mcp_servers:
--   filesystem:
--     command: npx
--     args: ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
--   brave-search:
--     command: npx
--     args: ["-y", "@modelcontextprotocol/server-brave-search"]
--     env:
--       BRAVE_API_KEY: ${BRAVE_API_KEY}
