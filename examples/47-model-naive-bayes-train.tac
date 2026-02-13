-- Example: Train Naive Bayes on IMDB (HuggingFace)

Model "imdb_nb" {
  data = {
    source = "hf",
    name = "imdb",
    train = "train",
    test = "test",
    shuffle = { train = true, test = true },
    limit = { train = 2000, test = 500 },
    seed = 42,
    text_field = "text",
    label_field = "label"
  },
  input = { text = "string" },
  output = { label = "string", confidence = "float" },
  candidates = {
    {
      name = "nb-tfidf",
      trainer = "naive_bayes",
      hyperparameters = {
        alpha = 1.0,
        max_features = 50000,
        ngram_min = 1,
        ngram_max = 2
      }
    }
  }
}
