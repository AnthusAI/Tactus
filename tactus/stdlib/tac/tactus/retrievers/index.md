# Retriever Modules

Tactus exposes Biblicus-backed retrievers as Lua modules so you can select a retriever explicitly at the top of your `.tac` file.

## Embedding index (file-backed)

```lua
local FilesystemCorpus = require("tactus.corpora.filesystem")
local vector = require("tactus.retrievers.embedding_index_file")

support_notes = FilesystemCorpus.Corpus {
  root = "corpora/support-notes",
  configuration = {
    pipeline = {
      extract = {
        -- extraction steps (optional)
      }
    }
  }
}

support_search = vector.Retriever {
  corpus = support_notes,
  configuration = {
    pipeline = {
      index = {
        embedding_provider = { provider_id = "hash-embedding", dimensions = 64 }
      },
      query = {
        limit = 3,
        maximum_total_characters = 1200
      }
    }
  }
}
```

## Embedding index (in-memory)

```lua
local FilesystemCorpus = require("tactus.corpora.filesystem")
local vector = require("tactus.retrievers.embedding_index_inmemory")

notes = FilesystemCorpus.Corpus {
  root = "corpora/notes",
  configuration = {
    pipeline = {
      extract = {
        -- extraction steps (optional)
      }
    }
  }
}

search = vector.Retriever {
  corpus = notes,
  configuration = {
    pipeline = {
      index = {
        embedding_provider = { provider_id = "hash-embedding", dimensions = 64 },
        maximum_cache_total_items = 5000
      },
      query = {
        limit = 2
      }
    }
  }
}
```

## SQLite full-text search

```lua
local FilesystemCorpus = require("tactus.corpora.filesystem")
local vector = require("tactus.retrievers.sqlite_full_text_search")

notes = FilesystemCorpus.Corpus {
  root = "corpora/notes",
  configuration = {
    pipeline = {
      extract = {
        -- extraction steps (optional)
      }
    }
  }
}

search = vector.Retriever {
  corpus = notes,
  configuration = {
    pipeline = {
      index = {
        snippet_characters = 400,
        chunk_size = 800,
        chunk_overlap = 200
      },
      query = {
        limit = 2,
        maximum_total_characters = 1200
      }
    }
  }
}
```

## TF vector (term-frequency)

```lua
local FilesystemCorpus = require("tactus.corpora.filesystem")
local vector = require("tactus.retrievers.tf_vector")

notes = FilesystemCorpus.Corpus {
  root = "corpora/notes",
  configuration = {
    pipeline = {
      extract = {
        -- extraction steps (optional)
      }
    }
  }
}

search = vector.Retriever {
  corpus = notes,
  configuration = {
    pipeline = {
      index = {
        -- optional index settings
      },
      query = {
        limit = 2,
        maximum_total_characters = 1200
      }
    }
  }
}
```
