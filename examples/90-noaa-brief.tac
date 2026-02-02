-- Simple NOAA AFD retrieval example.
-- Assumes you already ran:
--   python scripts/fetch_noaa_afd_corpus.py --wfo MFL --max-items 5
--   python scripts/prepare_noaa_afd_biblicus_corpus.py --wfo MFL --backend tf-vector --force

local vector = require("tactus.retrievers.tf_vector")

miami_afd = vector.Corpus {
  root = "tests/fixtures/noaa_afd_corpus/MFL"
}

miami_search = vector.Retriever {
  corpus           = miami_afd,
  limit            = 3,
  maximum_total_characters = 20000,
  include_metadata = true,
  metadata_fields  = { "published" }
}

miami_context = Context {
  packs            = { "miami_search" }
}

Miami = Agent {
  provider         = "openai",
  model            = "gpt-4o-mini",
  system_prompt    = "Use only the provided forecast discussion text as your source.",
  context          = miami_context
}

return Miami("Based only on the provided forecast discussion text, summarize what the weather has been like lately in Miami.")
