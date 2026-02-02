# Retriever Modules

Tactus exposes Biblicus-backed retrievers as Lua modules so you can select a backend explicitly at the top of your `.tac` file.

## Embedding index (file-backed)

```lua
local vector = require("tactus.retrievers.embedding_index_file")

support_notes = vector.Corpus {
  root = "corpora/support-notes",
  recipe = {
    embedding_provider = { provider_id = "hash-embedding", dimensions = 64 }
  }
}

support_search = vector.Retriever {
  corpus = support_notes,
  query = "{input.message}",
  limit = 3,
  maximum_total_characters = 1200
}
```

## Embedding index (in-memory)

```lua
local vector = require("tactus.retrievers.embedding_index_inmemory")

notes = vector.Corpus {
  root = "corpora/notes",
  recipe = {
    embedding_provider = { provider_id = "hash-embedding", dimensions = 64 },
    maximum_cache_total_items = 5000
  }
}

search = vector.Retriever {
  corpus = notes,
  query = "{input.message}",
  limit = 2
}
```

## SQLite full-text search

```lua
local vector = require("tactus.retrievers.sqlite_full_text_search")

notes = vector.Corpus {
  root = "corpora/notes",
  recipe = {
    snippet_characters = 400
  }
}

search = vector.Retriever {
  corpus = notes,
  query = "{input.message}",
  limit = 2,
  maximum_total_characters = 1200
}
```

## TF vector (term-frequency)

```lua
local vector = require("tactus.retrievers.tf_vector")

notes = vector.Corpus {
  root = "corpora/notes"
}

search = vector.Retriever {
  corpus = notes,
  query = "{input.message}",
  limit = 2,
  maximum_total_characters = 1200
}
```
