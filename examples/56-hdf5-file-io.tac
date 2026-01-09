--[[
Example: HDF5 File I/O

Demonstrates reading and writing HDF5 files with multiple datasets.
HDF5 is excellent for scientific data and large numerical arrays.

To run:
  tactus run examples/56-hdf5-file-io.tac
]]--

input {}

output {
        datasets_created = field.number{required = true},
        max_value = field.number{required = true}
    }

-- Create various numerical datasets

    -- Time series data
    local temperatures = {}
    local pressures = {}
    local timestamps = {}

    for i = 1, 100 do
        timestamps[i] = i * 3600  -- Hourly timestamps in seconds
        temperatures[i] = 20 + math.sin(i * 0.1) * 10 + (math.random() - 0.5) * 2
        pressures[i] = 1013 + math.cos(i * 0.1) * 20 + (math.random() - 0.5) * 5
    end

    -- Matrix data (simulating image or grid data)
    local grid_data = {}
    for row = 1, 50 do
        for col = 1, 50 do
            local index = (row - 1) * 50 + col
            grid_data[index] = math.sin(row * 0.1) * math.cos(col * 0.1) * 100
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
    Hdf5.write("scientific_data.h5", "time_series/temperatures", temperatures)
    Hdf5.write("scientific_data.h5", "time_series/pressures", pressures)
    Hdf5.write("scientific_data.h5", "time_series/timestamps", timestamps)

    Hdf5.write("scientific_data.h5", "grid/data", grid_data)

    Hdf5.write("scientific_data.h5", "coordinates/x", coordinates_x)
    Hdf5.write("scientific_data.h5", "coordinates/y", coordinates_y)
    Hdf5.write("scientific_data.h5", "coordinates/z", coordinates_z)

    Log.info("Created HDF5 file with multiple datasets")

    -- List all datasets in the file
    local datasets = Hdf5.list("scientific_data.h5")
    Log.info("Available datasets", {count = #datasets})

    for i, dataset_name in ipairs(datasets) do
        Log.debug("Dataset " .. i, {name = dataset_name})
    end

    -- Read specific datasets back
    local temp_data = Hdf5.read("scientific_data.h5", "time_series/temperatures")
    local grid_read = Hdf5.read("scientific_data.h5", "grid/data")

    -- Analyze temperature data
    local min_temp = temp_data[1]
    local max_temp = temp_data[1]
    local sum_temp = 0

    for i = 1, #temp_data do
        if temp_data[i] < min_temp then
            min_temp = temp_data[i]
        end
        if temp_data[i] > max_temp then
            max_temp = temp_data[i]
        end
        sum_temp = sum_temp + temp_data[i]
    end

    local avg_temp = sum_temp / #temp_data

    -- Find max value in grid
    local max_grid = grid_read[1]
    for i = 1, #grid_read do
        if grid_read[i] > max_grid then
            max_grid = grid_read[i]
        end
    end

    -- Create analysis results dataset
    local analysis_results = {
        min_temp,
        max_temp,
        avg_temp,
        max_grid,
        #datasets  -- number of datasets
    }

    Hdf5.write("scientific_data.h5", "analysis/results", analysis_results)

    -- Create metadata as a simple array
    local metadata = {
        20240115,  -- date as number
        #temp_data,  -- number of temperature readings
        #grid_read,  -- number of grid points
        1.0  -- version
    }

    Hdf5.write("scientific_data.h5", "metadata/info", metadata)

    Log.info("Analysis complete", {
        min_temperature = string.format("%.2f", min_temp),
        max_temperature = string.format("%.2f", max_temp),
        average_temperature = string.format("%.2f", avg_temp),
        max_grid_value = string.format("%.2f", max_grid)
    })

    return {
        datasets_created = #datasets + 2,  -- Original datasets plus 2 new ones
        max_value = math.floor(max_grid * 100) / 100
    }

Specifications([[
Feature: HDF5 File IO
  Scientific data storage with multiple datasets

  Scenario: Process scientific data
    Given the procedure has started
    When the procedure runs
    Then the procedure should complete successfully
    And the output datasets_created should be 9
]])
