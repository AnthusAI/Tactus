-- Simple NOAA AFD retrieval example (new workflow).
-- The NOAA fetch step is explicit, but extraction happens automatically on ingest
-- via the Corpus extraction pipeline. Retrievers that support index tasks expose
-- them automatically as CLI commands (index / index:<retriever_name>).

local FilesystemCorpus = require("tactus.corpora.filesystem")
local TfVector = require("tactus.retrievers.tf_vector")

python = Tool {
  use = "cli.python3",
  description = "Run python3 scripts"
}

FetchNoaaAfd = function(params)
  Log.info("FetchNoaaAfd: fetching NOAA AFD fixtures")
  python({
    args = {
      "scripts/fetch_noaa_afd_corpus.py",
      "--wfo", params.wfo,
      "--max-items", tostring(params.max_items),
      "--output", "tests/fixtures/noaa_afd",
    }
  })
  Log.info("FetchNoaaAfd: building Biblicus corpus + tf-vector index")
  python({
    args = {
      "scripts/prepare_noaa_afd_biblicus_corpus.py",
      "--retriever", "tf-vector",
      "--wfo", params.wfo,
      "--force",
    }
  })
  return {
    status = "ok",
    wfo = params.wfo,
    max_items = params.max_items,
  }
end

miami_afd = FilesystemCorpus.Corpus {
  root = "tests/fixtures/noaa_afd_corpus/MFL",
  configuration = {
    pipeline = {
      -- Extraction runs automatically on ingest.
      extract = {
        -- Placeholder for composed extraction steps.
      }
    }
  }
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

fetch = Task {
  entry = function()
    return FetchNoaaAfd({
      wfo = "MFL",
      max_items = 5,
      corpus = miami_afd
    })
  end
}

return Miami("Based only on the provided forecast discussion text, summarize what the weather has been like lately in Miami.")
