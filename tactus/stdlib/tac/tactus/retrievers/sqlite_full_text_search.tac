local base = require("tactus.retrievers.base")

return {
  Corpus = base.wrap_corpus({ backend_id = "sqlite-full-text-search" }),
  Retriever = base.wrap_retriever({ backend_id = "sqlite-full-text-search" }),
}
