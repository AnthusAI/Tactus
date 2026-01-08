--[[
Example: File I/O Operations

Demonstrates reading and writing various file formats in Tactus.
All file operations are restricted to the current working directory.

Available libraries:
- File: Raw text read/write (via FilePrimitive)
- Json: JSON encode/decode (via JsonPrimitive)
- Csv: CSV read/write with automatic header handling
- Tsv: Tab-separated values read/write
- Parquet: Apache Parquet format (requires pyarrow)
- Hdf5: HDF5 datasets (requires h5py)
- Excel: Excel spreadsheets (requires openpyxl)

To run:
  tactus run examples/52-file-io-basics.tac
]]--

input {}

output {
        records_processed = field.number{required = true},
        summary = field.string{required = true}
    }

-- Read CSV file (returns LuaList wrapper with {header=value} dicts)
    local data = Csv.read("examples/data/sample.csv")

    -- Get record count using :len() method
    local record_count = data:len()
    local high_performers = {}

    -- Iterate using 0-indexed access
    for i = 0, record_count - 1 do
        local row = data[i]
        local score = tonumber(row.score)
        if score >= 85 then
            -- Apply 10% bonus to high performers
            table.insert(high_performers, {
                name = row.name,
                original_score = score,
                bonus_score = math.floor(score * 1.1),
                category = row.category
            })
        end
    end

    Log.info("Loaded CSV data", {count = record_count})
    Log.info("Found high performers", {count = #high_performers})

    -- Write results to CSV
    Csv.write("output_high_performers.csv", high_performers)

    -- Write summary to JSON using File + Json.encode
    local summary_data = {
        total_records = record_count,
        high_performers = #high_performers,
        processed_at = os.date()
    }
    local json_str = Json.encode(summary_data)
    File.write("output_summary.json", json_str)

    -- Write raw text summary
    local summary_text = string.format(
        "Processed %d records, found %d high performers",
        record_count, #high_performers
    )
    File.write("output_summary.txt", summary_text)

    return {
        records_processed = record_count,
        summary = summary_text
    }

Specifications([[
Feature: File IO Operations
  Demonstrate reading and writing various file formats

  Scenario: Process CSV data and write results
    Given the procedure has started
    When the procedure runs
    Then the procedure should complete successfully
    And the output records_processed should be 5
]])
