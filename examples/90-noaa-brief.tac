-- Simple NOAA AFD retrieval example (new workflow).
-- The NOAA fetch step is explicit, but extraction happens automatically on ingest
-- via the Corpus extraction pipeline. Retrievers that support index tasks expose
-- them automatically as CLI commands (index / index:<retriever_name>).

local FilesystemCorpus = require("tactus.corpora.filesystem")
local TfVector = require("tactus.retrievers.tf_vector")

FetchNoaaAfd = Tool {
  use = "plugin.noaa.fetch_noaa_afd",
  description = "Fetch NOAA AFD fixtures and import into Biblicus"
}

miami_afd = FilesystemCorpus.Corpus {
  root = "tests/fixtures/noaa_afd_corpus/MFL"
}

miami_search = TfVector.Retriever {
  corpus = miami_afd,
  configuration = {
    pipeline = {
      index = {
        -- Indexing configuration lives here when needed.
      },
      query = {
        limit = 3,
        maximum_total_characters = 20000,
        include_metadata = true,
        metadata_fields = { "published" }
      }
    }
  }
}

miami_context = Context {
  packs = { "miami_search" }
}

Miami = Agent {
  provider = "openai",
  model = "gpt-4o-mini",
  system_prompt = "Use only the provided forecast discussion text as your source.",
  context = miami_context
}

Task "fetch" {
  entry = function()
    return FetchNoaaAfd({
      wfo = "MFL",
      max_items = 5,
    })
  end
}

return Miami("Based only on the provided forecast discussion text, summarize what the weather has been like lately in Miami.")
