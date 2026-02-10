-- Biblicus dependency block when no load handler exists.
-- Run:
--   tactus run --auto-deps examples/97-task-deps-biblicus-blocked.tac index

local FilesystemCorpus = require("tactus.corpora.filesystem")
local TfVector = require("tactus.retrievers.tf_vector")

miami_afd = FilesystemCorpus.Corpus {
  root = "tests/fixtures/empty_corpus"
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

return { status = "ready" }
