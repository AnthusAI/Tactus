--[[
Example: HDF5 File I/O

Demonstrates creating HDF5 files with multiple datasets.
HDF5 is excellent for scientific data and large numerical arrays.

To run:
  tactus run examples/56-hdf5-file-io.tac
]]--

local hdf5 = require("tactus.io.hdf5")

Procedure {
    input = {
    },
    output = {
            datasets_created = field.number{required = true},
            max_value = field.number{required = true}
    },
    function(input)

    -- Create various numerical datasets

        -- Time series data
        local temperatures = {}
        local pressures = {}
        local timestamps = {}

        local max_temp = -999
        for i = 1, 100 do
            timestamps[i] = i * 3600  -- Hourly timestamps in seconds
            temperatures[i] = 20 + math.sin(i * 0.1) * 10 + (math.random() - 0.5) * 2
            pressures[i] = 1013 + math.cos(i * 0.1) * 20 + (math.random() - 0.5) * 5
            if temperatures[i] > max_temp then
                max_temp = temperatures[i]
            end
        end

        -- Matrix data (simulating image or grid data)
        local grid_data = {}
        local max_grid = -999
        for row = 1, 50 do
            for col = 1, 50 do
                local index = (row - 1) * 50 + col
                grid_data[index] = math.sin(row * 0.1) * math.cos(col * 0.1) * 100
                if grid_data[index] > max_grid then
                    max_grid = grid_data[index]
                end
            end
        end

        -- Vector data
        local coordinates_x = {}
        local coordinates_y = {}
        local coordinates_z = {}

        for i = 1, 200 do
            local angle = (i - 1) * math.pi / 100
            coordinates_x[i] = math.cos(angle) * 10
            coordinates_y[i] = math.sin(angle) * 10
            coordinates_z[i] = i * 0.1
        end

        -- Write datasets to HDF5 file
        hdf5.write("output/scientific_data.h5", "time_series/temperatures", temperatures)
        hdf5.write("output/scientific_data.h5", "time_series/pressures", pressures)
        hdf5.write("output/scientific_data.h5", "time_series/timestamps", timestamps)

        hdf5.write("output/scientific_data.h5", "grid/data", grid_data)

        hdf5.write("output/scientific_data.h5", "coordinates/x", coordinates_x)
        hdf5.write("output/scientific_data.h5", "coordinates/y", coordinates_y)
        hdf5.write("output/scientific_data.h5", "coordinates/z", coordinates_z)

        Log.info("Created HDF5 file with multiple datasets")

        -- We know we created 7 datasets
        local dataset_count = 7

        -- Write analysis results
        local analysis_results = {max_temp, max_grid}
        hdf5.write("output/scientific_data.h5", "analysis/results", analysis_results)

        -- Write metadata
        local metadata = {20240115, 100, 2500, 1.0}
        hdf5.write("output/scientific_data.h5", "metadata/info", metadata)

        Log.info("Analysis complete", {
            max_temperature = string.format("%.2f", max_temp),
            max_grid_value = string.format("%.2f", max_grid)
        })

        return {
            datasets_created = dataset_count + 2,  -- Original 7 datasets plus 2 new ones
            max_value = math.floor(max_grid * 100) / 100
        }
    end
}

Specification([[
Feature: HDF5 File IO
  Scientific data storage with multiple datasets

  Scenario: Process scientific data
    Given the procedure has started
    When the procedure runs
    Then the procedure should complete successfully
    And the output datasets_created should be 9
]])
