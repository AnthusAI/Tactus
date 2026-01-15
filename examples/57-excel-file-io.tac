--[[
Example: Excel File I/O

Demonstrates reading and writing Excel spreadsheets with multiple sheets.
Excel format is widely used for business data and reporting.

To run:
  tactus run examples/57-excel-file-io.tac
]]--

local excel = require("tactus.io.excel")

Procedure {
    input = {
    },
    output = {
            total_revenue = field.number{required = true},
            profit_margin = field.number{required = true}
    },
    function(input)

    -- Create sales data for Q1
        local q1_sales = {
            {month = "January", product = "Widget A", units = 150, unit_price = 29.99, cost_per_unit = 15.00},
            {month = "January", product = "Widget B", units = 85, unit_price = 49.99, cost_per_unit = 25.00},
            {month = "January", product = "Widget C", units = 200, unit_price = 19.99, cost_per_unit = 8.00},
            {month = "February", product = "Widget A", units = 175, unit_price = 29.99, cost_per_unit = 15.00},
            {month = "February", product = "Widget B", units = 92, unit_price = 49.99, cost_per_unit = 25.00},
            {month = "February", product = "Widget C", units = 225, unit_price = 19.99, cost_per_unit = 8.00},
            {month = "March", product = "Widget A", units = 195, unit_price = 29.99, cost_per_unit = 15.00},
            {month = "March", product = "Widget B", units = 110, unit_price = 49.99, cost_per_unit = 25.00},
            {month = "March", product = "Widget C", units = 250, unit_price = 19.99, cost_per_unit = 8.00}
        }

        -- Calculate revenue and profit for each row
        for _, row in ipairs(q1_sales) do
            row.revenue = row.units * row.unit_price
            row.cost = row.units * row.cost_per_unit
            row.profit = row.revenue - row.cost
        end

        -- Write to Excel with Q1 sheet
        excel.write("output/sales_report.xlsx", q1_sales, {sheet = "Q1_Sales"})
        Log.info("Created Excel file with Q1 sales data")

        -- Read it back
        local loaded_sales = excel.read("output/sales_report.xlsx", {sheet = "Q1_Sales"})

        -- Process the data
        local monthly_summary = {}
        local product_summary = {}
        local total_revenue = 0
        local total_cost = 0

        for i = 1, #loaded_sales do
            local row = loaded_sales[i]
            local revenue = tonumber(row.revenue)
            local cost = tonumber(row.cost)
            local profit = tonumber(row.profit)

            total_revenue = total_revenue + revenue
            total_cost = total_cost + cost

            -- Aggregate by month
            if not monthly_summary[row.month] then
                monthly_summary[row.month] = {revenue = 0, cost = 0, profit = 0}
            end
            monthly_summary[row.month].revenue = monthly_summary[row.month].revenue + revenue
            monthly_summary[row.month].cost = monthly_summary[row.month].cost + cost
            monthly_summary[row.month].profit = monthly_summary[row.month].profit + profit

            -- Aggregate by product
            if not product_summary[row.product] then
                product_summary[row.product] = {units = 0, revenue = 0, profit = 0}
            end
            product_summary[row.product].units = product_summary[row.product].units + tonumber(row.units)
            product_summary[row.product].revenue = product_summary[row.product].revenue + revenue
            product_summary[row.product].profit = product_summary[row.product].profit + profit
        end

        -- Create monthly summary sheet data
        local monthly_data = {}
        for month, data in pairs(monthly_summary) do
            table.insert(monthly_data, {
                month = month,
                revenue = string.format("%.2f", data.revenue),
                cost = string.format("%.2f", data.cost),
                profit = string.format("%.2f", data.profit),
                margin = string.format("%.1f%%", (data.profit / data.revenue) * 100)
            })
        end

        -- Create product summary sheet data
        local product_data = {}
        for product, data in pairs(product_summary) do
            table.insert(product_data, {
                product = product,
                total_units = data.units,
                total_revenue = string.format("%.2f", data.revenue),
                total_profit = string.format("%.2f", data.profit),
                avg_profit_per_unit = string.format("%.2f", data.profit / data.units)
            })
        end

        -- Create a new Excel file with multiple sheets
        excel.write("output/sales_analysis.xlsx", monthly_data, {sheet = "Monthly_Summary"})

        -- Read back the first file to add more sheets
        -- Note: Our current implementation doesn't support appending sheets,
        -- so we'll create separate files for now
        excel.write("output/product_analysis.xlsx", product_data, {sheet = "Product_Summary"})

        -- List sheets in the original file
        local sheets = excel.sheets("output/sales_report.xlsx")
        -- sheets is a Python list, just log it directly
        Log.info("Available sheets in output/sales_report.xlsx")

        -- Create executive summary
        local total_profit = total_revenue - total_cost
        local profit_margin = (total_profit / total_revenue) * 100

        local executive_summary = {
            {metric = "Total Revenue", value = string.format("$%.2f", total_revenue)},
            {metric = "Total Cost", value = string.format("$%.2f", total_cost)},
            {metric = "Total Profit", value = string.format("$%.2f", total_profit)},
            {metric = "Profit Margin", value = string.format("%.1f%%", profit_margin)},
            {metric = "Total Transactions", value = tostring(#loaded_sales)}
        }

        excel.write("output/executive_summary.xlsx", executive_summary, {sheet = "Summary"})

        Log.info("Analysis complete", {
            total_revenue = string.format("$%.2f", total_revenue),
            profit_margin = string.format("%.1f%%", profit_margin)
        })

        return {
            total_revenue = math.floor(total_revenue),
            profit_margin = math.floor(profit_margin * 10) / 10
        }
    end
}

Specification([[
Feature: Excel File IO
  Business data processing with spreadsheets

  Scenario: Process sales data
    Given the procedure has started
    When the procedure runs
    Then the procedure should complete successfully
    And the output total_revenue should exist
    And the output profit_margin should exist
]])
