# File I/O in Tactus

Tactus provides safe file I/O operations for reading and writing data files. All file operations are restricted to the current working directory and below for security.

## Available Libraries

| Library | Format | Python Backend | Description |
|---------|--------|----------------|-------------|
| `File` | Raw text | stdlib | Read/write raw text files |
| `Json` | JSON | stdlib | Encode/decode JSON data |
| `Csv` | CSV | stdlib csv | Read/write CSV with headers |
| `Tsv` | TSV | stdlib csv | Read/write tab-separated values |
| `Parquet` | Parquet | pyarrow | Read/write Apache Parquet files |
| `Hdf5` | HDF5 | h5py | Read/write HDF5 datasets |
| `Excel` | Excel | openpyxl | Read/write Excel spreadsheets |

## Quick Start

```lua
-- Read CSV file
local data = Csv.read("data.csv")

-- Process data
for i = 0, #data - 1 do  -- Python lists are 0-indexed
    local row = data[i]
    Log.info("Name: " .. row.name .. ", Score: " .. row.score)
end

-- Write results
Csv.write("output.csv", processed_data)

-- Read/write raw text
local content = File.read("config.txt")
File.write("output.txt", "Hello, world!")

-- JSON encode/decode
local json_str = Json.encode({name = "Alice", score = 95})
local decoded = Json.decode(json_str)
```

## API Reference

### File (Raw Text)

```lua
-- Read file contents as string
local content = File.read("data.txt")

-- Write string to file
File.write("output.txt", "Hello, world!")

-- Check if file exists
if File.exists("data.txt") then
    -- file exists
end

-- Get file size in bytes
local size = File.size("data.txt")
```

### Json

```lua
-- Encode Lua table to JSON string
local json_str = Json.encode({name = "Alice", scores = {85, 92, 78}})

-- Decode JSON string to Lua table
local data = Json.decode('{"name": "Bob", "active": true}')
Log.info(data.name)  -- "Bob"
```

### Csv

```lua
-- Read CSV file (returns array of {header=value} dictionaries)
local data = Csv.read("data.csv")

-- Access rows (0-indexed Python list)
local first_row = data[0]
Log.info(first_row.name)

-- Write CSV from array of dictionaries
local results = {
    {name = "Alice", score = 95},
    {name = "Bob", score = 87}
}
Csv.write("output.csv", results)

-- Write with explicit header order
Csv.write("output.csv", results, {headers = {"score", "name"}})
```

### Tsv

Same API as CSV, but uses tab as delimiter:

```lua
local data = Tsv.read("data.tsv")
Tsv.write("output.tsv", results)
```

### Parquet

```lua
-- Read Parquet file
local data = Parquet.read("data.parquet")

-- Write Parquet file
Parquet.write("output.parquet", data)
```

### Hdf5

```lua
-- Read specific dataset from HDF5 file
local numbers = Hdf5.read("data.h5", "dataset_name")

-- Write data to HDF5 dataset
Hdf5.write("output.h5", "numbers", {1, 2, 3, 4, 5})

-- List all datasets in file
local datasets = Hdf5.list("data.h5")
```

### Excel

```lua
-- Read first sheet from Excel file
local data = Excel.read("data.xlsx")

-- Read specific sheet
local sheet2 = Excel.read("data.xlsx", {sheet = "Sheet2"})

-- Write Excel file
Excel.write("output.xlsx", data)

-- Write to specific sheet
Excel.write("output.xlsx", data, {sheet = "Results"})

-- List sheet names
local sheets = Excel.sheets("data.xlsx")
```

## Important Notes

### Python List Indexing

When reading data (CSV, Parquet, etc.), the returned data is a Python list, which is **0-indexed** when accessed from Lua:

```lua
local data = Csv.read("data.csv")

-- Correct: 0-indexed access
local first = data[0]
local second = data[1]

-- Iterate with ipairs-style loop
for i = 0, #data - 1 do
    local row = data[i]
    -- process row
end
```

### Determinism Warning

File operations are non-deterministic because file contents can change between procedure executions. For durable workflows, wrap file operations in `Step.checkpoint()`:

```lua
-- Recommended for durable workflows
local data = Step.checkpoint(function()
    return Csv.read("data.csv")
end)
```

### Security

All file operations are restricted to the current working directory:
- Absolute paths outside the working directory are blocked
- Path traversal (`../`) attempts are blocked
- Only relative paths within the working directory are allowed

```lua
-- These will fail with PermissionError:
File.read("/etc/passwd")           -- Absolute path outside cwd
File.read("../../../etc/passwd")   -- Path traversal
Csv.read("../../data.csv")         -- Escaping working directory
```

## Example

See [examples/52-file-io-basics.tac](../examples/52-file-io-basics.tac) for a complete example demonstrating:
- Reading CSV data
- Processing and filtering records
- Writing results to multiple formats

```bash
tactus run examples/52-file-io-basics.tac
```
