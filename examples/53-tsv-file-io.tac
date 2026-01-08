--[[
Example: TSV (Tab-Separated Values) File I/O

Demonstrates reading and writing TSV files.
TSV is useful for data that may contain commas in values.

To run:
  tactus run examples/53-tsv-file-io.tac
]]--

input {}

output {
        records_processed = field.number{required = true},
        summary = field.string{required = true}
    }

-- Create sample TSV data
    local inventory_data = {
        {product = "Laptop, Pro Model", quantity = "15", price = "1299.99", location = "Warehouse A"},
        {product = "Mouse, Wireless", quantity = "45", price = "29.99", location = "Warehouse B"},
        {product = "Keyboard, Mechanical", quantity = "32", price = "89.99", location = "Warehouse A"},
        {product = "Monitor, 27\"", quantity = "8", price = "399.99", location = "Warehouse C"},
        {product = "Cable, USB-C", quantity = "120", price = "12.99", location = "Warehouse B"}
    }

    -- Write TSV file
    Tsv.write("inventory.tsv", inventory_data)
    Log.info("Created inventory TSV file")

    -- Read it back
    local loaded_data = Tsv.read("inventory.tsv")
    local total_items = 0
    local total_value = 0

    -- Process inventory (0-indexed access)
    for i = 0, loaded_data:len() - 1 do
        local item = loaded_data[i]
        local qty = tonumber(item.quantity)
        local price = tonumber(item.price)
        total_items = total_items + qty
        total_value = total_value + (qty * price)

        Log.debug("Product inventory", {
            product = item.product,
            quantity = qty,
            location = item.location
        })
    end

    -- Write summary with custom header order
    local summary_data = {
        {metric = "Total Products", value = tostring(loaded_data:len())},
        {metric = "Total Items", value = tostring(total_items)},
        {metric = "Total Value", value = string.format("$%.2f", total_value)}
    }

    Tsv.write("inventory_summary.tsv", summary_data, {
        headers = {"metric", "value"}
    })

    local summary = string.format(
        "Processed %d products, %d total items worth $%.2f",
        loaded_data:len(), total_items, total_value
    )

    return {
        records_processed = loaded_data:len(),
        summary = summary
    }

Specifications([[
Feature: TSV File IO
  Handle tab-separated values with commas in data

  Scenario: Process inventory data
    Given the procedure has started
    When the procedure runs
    Then the procedure should complete successfully
    And the output records_processed should be 5
]])
