local base = require("tactus.retrievers.base")

return {
  Corpus = base.wrap_corpus({ backend_id = "tf-vector" }),
  Retriever = base.wrap_retriever({ backend_id = "tf-vector" }),
}
