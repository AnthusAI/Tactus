local embedding_index_file = require("tactus.retrievers.embedding_index_file")
local embedding_index_inmemory = require("tactus.retrievers.embedding_index_inmemory")
local sqlite_full_text_search = require("tactus.retrievers.sqlite_full_text_search")
local tf_vector = require("tactus.retrievers.tf_vector")

return {
  EmbeddingIndexFile = embedding_index_file,
  EmbeddingIndexInMemory = embedding_index_inmemory,
  SqliteFullTextSearch = sqlite_full_text_search,
  TfVector = tf_vector,
}
