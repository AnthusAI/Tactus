-- Example: Compare Naive Bayes vs HF sequence classifier on IMDB

Model "imdb_compare" {
  type = "registry",
  name = "imdb_compare",
  version = "latest",
  input = { text = "string" },
  output = { label = "string", confidence = "float" },
  training = {
    data = {
      source = "hf",
      name = "imdb",
      train = "train",
      test = "test",
      text_field = "text",
      label_field = "label",
      shuffle = { train = true, test = true },
      limit = { train = 10000, test = 2000 },
      seed = 42
    },
    candidates = {
      {
        name = "nb_tfidf",
        trainer = "naive_bayes",
        hyperparameters = {
          alpha = 1.0,
          max_features = 50000,
          ngram_min = 1,
          ngram_max = 2
        }
      },
      {
        name = "hf_distilbert",
        trainer = "hf_sequence_classifier",
        hyperparameters = {
          model = "distilbert-base-uncased",
          labels = {"negative", "positive"},
          epochs = 1,
          batch_size = 8,
          learning_rate = 2e-5,
          max_length = 256,
          padding = "max_length",
          truncation = true,
          training_args = {
            evaluation_strategy = "no",
            save_strategy = "no",
            logging_steps = 50
          }
        }
      }
    }
  }
}
