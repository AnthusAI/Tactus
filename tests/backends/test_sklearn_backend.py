from pathlib import Path

from tactus.backends.sklearn_backend import SklearnModelBackend


def test_sklearn_backend_predicts_label(tmp_path):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.naive_bayes import MultinomialNB
    import joblib

    texts = ["good movie", "bad movie", "great film", "terrible film"]
    labels = ["positive", "negative", "positive", "negative"]

    vectorizer = TfidfVectorizer()
    x_train = vectorizer.fit_transform(texts)
    model = MultinomialNB()
    model.fit(x_train, labels)

    artifact_path = Path(tmp_path) / "model.joblib"
    joblib.dump({"vectorizer": vectorizer, "model": model}, artifact_path)

    backend = SklearnModelBackend(path=str(artifact_path), labels=["negative", "positive"])
    result = backend.predict_sync("good film")

    assert isinstance(result, dict)
    assert "label" in result
