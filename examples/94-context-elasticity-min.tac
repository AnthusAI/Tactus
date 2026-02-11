-- Minimal Context budget demo with a single pack budget.
-- Requires NOAA fixtures (see tests/fixtures/noaa_afd_corpus for local copy).

local FilesystemCorpus = require("tactus.corpora.filesystem")
local TfVector = require("tactus.retrievers.tf_vector")

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

budgeted_context = Context {
  packs = { "miami_search" },
  policy = {
    pack_budget = { default_max_tokens = 200 }
  },
  messages = {
    { type = "system", content = "Use only the provided forecast discussion text as your source." },
    { type = "context", name = "miami_search" },
    { type = "history" },
    { type = "user", template = "Question: {input.question}" }
  }
}

Brief = Agent {
  provider = "openai",
  model = "gpt-4o-mini",
  system_prompt = "You are a helpful assistant.",
  context = budgeted_context
}

Task "run" {
  entry = function()
    return Brief(
      "Based only on the provided forecast discussion text, summarize what the weather has been like lately in Miami."
    )
  end
}

return Brief(
  "Based only on the provided forecast discussion text, summarize what the weather has been like lately in Miami."
)
