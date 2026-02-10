-- Biblicus task dependencies (load -> extract -> index).
-- Run:
--   tactus examples/97-task-deps-biblicus.tac index --auto-deps
--   tactus examples/97-task-deps-biblicus.tac index:miami_search --auto-deps

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
      query = {
        limit = 4,
        maximum_total_characters = 20000
      }
    }
  }
}

miami_search_alt = TfVector.Retriever {
  corpus = miami_afd,
  configuration = {
    pipeline = {
      query = {
        limit = 8,
        maximum_total_characters = 40000
      }
    }
  }
}

Task "fetch" {
  provides = { kind = "load", corpus = "miami_afd" },
  entry = function()
    return FetchNoaaAfd({
      wfo = "MFL",
      max_items = 5,
    })
  end
}

return { status = "ready" }
