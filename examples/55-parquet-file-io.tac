--[[
Example: Parquet File I/O

Demonstrates reading and writing Apache Parquet files.
Parquet is a columnar storage format that's efficient for analytics.

To run:
  tactus run examples/55-parquet-file-io.tac
]]--

local parquet = require("tactus.io.parquet")

Procedure {
    input = {
    },
    output = {
            records_written = field.number{required = true},
            average_temperature = field.number{required = true}
    },
    function(input)

    -- Create sensor data with various data types
        local sensor_data = {}

        -- Generate sample sensor readings
        for day = 1, 30 do
            for hour = 0, 23 do
                local temp_base = 20 + math.sin(hour * math.pi / 12) * 5
                local humidity_base = 60 + math.cos(hour * math.pi / 12) * 15

                table.insert(sensor_data, {
                    timestamp = string.format("2024-01-%02d %02d:00:00", day, hour),
                    sensor_id = "SENSOR_" .. (hour % 3 + 1),
                    temperature = temp_base + (math.random() - 0.5) * 2,
                    humidity = humidity_base + (math.random() - 0.5) * 5,
                    pressure = 1013.25 + (math.random() - 0.5) * 10,
                    is_valid = math.random() > 0.1,  -- 90% valid readings
                    location = (hour % 3 == 0) and "Zone_A" or ((hour % 3 == 1) and "Zone_B" or "Zone_C")
                })
            end
        end

        -- Write to Parquet format
        parquet.write("output/sensor_data.parquet", sensor_data)
        Log.info("Created Parquet file", {records = #sensor_data})

        -- Read it back
        local loaded_data = parquet.read("output/sensor_data.parquet")

        -- Analyze the data
        local total_temp = 0
        local valid_count = 0
        local zone_counts = {Zone_A = 0, Zone_B = 0, Zone_C = 0}

        for i = 1, #loaded_data do
            local reading = loaded_data[i]

            if reading.is_valid then
                valid_count = valid_count + 1
                total_temp = total_temp + reading.temperature
            end

            zone_counts[reading.location] = zone_counts[reading.location] + 1
        end

        local average_temp = total_temp / valid_count

        -- Create aggregated summary
        local summary = {}
        for zone, count in pairs(zone_counts) do
            table.insert(summary, {
                zone = zone,
                reading_count = count,
                percentage = string.format("%.1f%%", (count / #loaded_data) * 100)
            })
        end

        -- Write summary to Parquet
        parquet.write("output/sensor_summary.parquet", summary)

        Log.info("Data analysis complete", {
            total_records = #loaded_data,
            valid_records = valid_count,
            average_temperature = string.format("%.2f", average_temp)
        })

        -- Also create a detailed report
        local report_data = {
            {
                metric = "Total Readings",
                value = #loaded_data,
                unit = "count"
            },
            {
                metric = "Valid Readings",
                value = valid_count,
                unit = "count"
            },
            {
                metric = "Average Temperature",
                value = average_temp,
                unit = "celsius"
            },
            {
                metric = "Data Quality",
                value = (valid_count / #loaded_data) * 100,
                unit = "percent"
            }
        }

        parquet.write("output/sensor_report.parquet", report_data)

        return {
            records_written = #sensor_data,
            average_temperature = math.floor(average_temp * 100) / 100
        }
    end
}

Specification([[
Feature: Parquet File IO
  Efficient columnar storage for analytics data

  Scenario: Process sensor data
    Given the procedure has started
    When the procedure runs
    Then the procedure should complete successfully
    And the output records_written should be 720
]])
