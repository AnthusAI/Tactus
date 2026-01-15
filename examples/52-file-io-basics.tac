--[[
Example: File I/O Operations

Demonstrates reading and writing various file formats in Tactus.
All file operations are restricted to the current working directory.

Available libraries (via require):
- tactus.io.file: Raw text read/write
- tactus.io.json: JSON encode/decode
- tactus.io.csv: CSV read/write with automatic header handling
- tactus.io.tsv: Tab-separated values read/write
- tactus.io.parquet: Apache Parquet format (requires pyarrow)
- tactus.io.hdf5: HDF5 datasets (requires h5py)
- tactus.io.excel: Excel spreadsheets (requires openpyxl)

To run:
  tactus run examples/52-file-io-basics.tac
]]--

local csv = require("tactus.io.csv")
local json = require("tactus.io.json")
local file = require("tactus.io.file")

Procedure {
    input = {
    },
    output = {
            records_processed = field.number{required = true},
            summary = field.string{required = true}
    },
    function(input)

        -- Read CSV file (returns list of {header=value} dicts)
        -- Path is relative to the procedure file's directory
        local data = csv.read("data/sample.csv")

        -- Get record count
        local record_count = #data
        local high_performers = {}

        -- Iterate through records
        for i = 1, record_count do
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

        -- Write results to CSV (output/ folder is gitignored)
        csv.write("output/high_performers.csv", high_performers)

        -- Write summary to JSON
        local summary_data = {
            total_records = record_count,
            high_performers = #high_performers,
            processed_at = os.date()
        }
        json.write("output/summary.json", summary_data)

        -- Write raw text summary
        local summary_text = string.format(
            "Processed %d records, found %d high performers",
            record_count, #high_performers
        )
        file.write("output/summary.txt", summary_text)

        return {
            records_processed = record_count,
            summary = summary_text
        }
    end
}

Specification([[
Feature: File IO Operations
  Demonstrate reading and writing various file formats

  Scenario: Process CSV data and write results
    Given the procedure has started
    When the procedure runs
    Then the procedure should complete successfully
    And the output records_processed should be 5
]])
