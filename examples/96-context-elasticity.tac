-- Demonstrate elastic Context packs with different budgets.
-- Requires NOAA AFD fixtures (run examples/90-noaa-brief.tac fetch first).

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
        maximum_total_characters = 20000,
        include_metadata = true,
        metadata_fields = { "published" }
      }
    }
  }
}

short_context = Context {
  packs = { "miami_search" },
  policy = {
    input_budget = { max_tokens = 1600 },
    pack_budget = { default_max_tokens = 200 },
    overflow = "compact"
  },
  messages = {
    {
      type = "system",
      content = "Use only the provided forecast discussion text as your source."
    },
    { type = "context", name = "miami_search" },
    { type = "history" },
    {
      type = "user",
      template = "Question: {input.question}"
    }
  }
}

long_context = Context {
  packs = { "miami_search" },
  policy = {
    input_budget = { max_tokens = 3600 },
    pack_budget = { default_max_tokens = 1200 },
    overflow = "compact"
  },
  messages = {
    {
      type = "system",
      content = "Use only the provided forecast discussion text as your source."
    },
    { type = "context", name = "miami_search" },
    { type = "history" },
    {
      type = "user",
      template = "Question: {input.question}"
    }
  }
}

ShortBrief = Agent {
  provider = "openai",
  model = "gpt-4o-mini",
  system_prompt = "You are a helpful assistant.",
  context = short_context
}

LongBrief = Agent {
  provider = "openai",
  model = "gpt-4o-mini",
  system_prompt = "You are a helpful assistant.",
  context = long_context
}

Task "run_short" {
  entry = function()
    return ShortBrief(
      "Based only on the provided forecast discussion text, summarize what the weather has been like lately in Miami."
    )
  end
}

Task "run_long" {
  entry = function()
    return LongBrief(
      "Based only on the provided forecast discussion text, summarize what the weather has been like lately in Miami."
    )
  end
}

return ShortBrief(
  "Based only on the provided forecast discussion text, summarize what the weather has been like lately in Miami."
)
