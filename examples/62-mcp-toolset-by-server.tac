-- Example: MCP Server Toolset Identification by Server Name
-- Demonstrates proper identification of MCP toolsets by server name

-- Define completion tool
Tool "done" { use = "tactus.done" }

-- Define toolsets that reference specific MCP servers
-- Note: These require actual MCP servers to be configured in .tac.yml
Toolset "filesystem_tools" {
    use = "mcp.filesystem"  -- Reference filesystem MCP server
}

Toolset "search_tools" {
    use = "mcp.brave-search"  -- Reference brave-search MCP server
}

-- Agent that uses MCP toolsets by server name
Agent "researcher" {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[You are a research assistant with access to filesystem and search tools.

Available MCP toolsets:
- Filesystem tools (prefixed with filesystem_)
- Search tools (prefixed with brave-search_)

Use these tools to help with research tasks.
When done, call the done tool.]],

    toolsets = {"filesystem_tools", "search_tools", "done"}
}

-- Alternative: Direct reference to MCP server in agent
Agent "file_manager" {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[You are a file management assistant.

Use filesystem tools to manage files.
When done, call the done tool.]],

    -- Directly reference MCP server (registered by server name)
    toolsets = {"filesystem", "done"}
}

-- Main procedure

input {
        task = field.string{
            default = "list files",
            description = "Task to perform: 'list files' or 'search web'"
        }
    }

output {
        result = field.string{required = true, description = "Task result"},
        mcp_tools_used = field.array{description = "List of MCP tools used"},
        completed = field.boolean{required = true, description = "Whether task completed"}
    }

Log.info("Starting MCP toolset identification demo", {task = input.task})

        -- Choose agent based on task
        local agent_name = "researcher"
        local message = ""

        if input.task == "list files" then
            agent_name = "file_manager"
            message = "Please list the files in the current directory."
        elseif input.task == "search web" then
            agent_name = "researcher"
            message = "Please search for 'Lua programming language' and summarize what you find."
        else
            message = input.task
        end

        -- Run agent with limit
        local max_turns = 3
        local turn_count = 0
        local result

        repeat
            if turn_count == 0 then
                result = Agent(agent_name).turn({initial_message = message})
            else
                result = Agent(agent_name).turn()
            end
            turn_count = turn_count + 1
        until Tool.called("done") or turn_count >= max_turns

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

        if Tool.called("done") then
            completed = true
            local call = Tool.last_call("done")
            if call and call.args then
                local ok, reason = pcall(function() return call.args["reason"] end)
                if ok and reason then
                    answer = reason
                end
            end
        elseif result and result.text then
            answer = result.text
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
Specifications([[
Feature: MCP Server Toolset Identification
  Demonstrate proper identification of MCP toolsets by server name

  Scenario: Use filesystem MCP server by name
    Given the procedure has started
    When the procedure runs with task "list files"
    Then the output completed should be True
    And at least one filesystem MCP tool should be called

  Scenario: Use search MCP server by name
    Given the procedure has started
    When the procedure runs with task "search web"
    Then the output completed should be True
    And at least one search MCP tool should be called

  Scenario: MCP toolsets are properly namespaced
    Given the procedure has started
    When the procedure runs
    Then MCP tools should have server name prefixes
    And different MCP servers should not conflict
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
