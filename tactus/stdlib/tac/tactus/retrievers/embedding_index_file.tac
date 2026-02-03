local base = require("tactus.retrievers.base")

return {
  Corpus = base.wrap_corpus({}),
  Retriever = base.wrap_retriever({ retriever_id = "embedding-index-file" }),
}
