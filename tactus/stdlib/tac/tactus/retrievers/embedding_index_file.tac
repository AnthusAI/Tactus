local base = require("tactus.retrievers.base")

return {
  Corpus = base.wrap_corpus({ backend_id = "embedding-index-file" }),
  Retriever = base.wrap_retriever({ backend_id = "embedding-index-file" }),
}
