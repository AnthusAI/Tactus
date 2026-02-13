import sys
from types import SimpleNamespace

from tactus.backends.hf_transformers_backend import HFTransformersBackend


def test_hf_transformers_backend_predicts_label(monkeypatch):
    class FakeTensor:
        def __init__(self, data):
            self.data = data

        def to(self, device):
            return self

        def __getitem__(self, index):
            return FakeTensor(self.data[index])

    class FakeIndex:
        def __init__(self, value):
            self._value = value

        def __int__(self):
            return self._value

    class FakeModel:
        def __init__(self):
            self.config = SimpleNamespace(id2label={0: "negative", 1: "positive"})

        def to(self, device):
            return self

        def __call__(self, **kwargs):
            return SimpleNamespace(logits=FakeTensor([[0.1, 2.0]]))

    class FakeTokenizer:
        def __call__(self, text, return_tensors=None, truncation=None):
            return {"input_ids": FakeTensor([[1, 2, 3]])}

    class FakeTorch:
        @staticmethod
        def no_grad():
            class Ctx:
                def __enter__(self):
                    return None

                def __exit__(self, exc_type, exc, tb):
                    return False

            return Ctx()

        @staticmethod
        def softmax(logits, dim=-1):
            return FakeTensor([[0.1, 0.9]])

        @staticmethod
        def max(probs, dim=-1):
            return 0.9, FakeIndex(1)

    class FakeAutoModel:
        @staticmethod
        def from_pretrained(model_name, revision=None):
            return FakeModel()

    def fake_auto_tokenizer_from_pretrained(model_name, revision=None):
        return FakeTokenizer()

    monkeypatch.setitem(
        sys.modules,
        "transformers",
        SimpleNamespace(
            AutoTokenizer=SimpleNamespace(from_pretrained=fake_auto_tokenizer_from_pretrained),
            AutoModelForSequenceClassification=FakeAutoModel,
        ),
    )
    monkeypatch.setitem(sys.modules, "torch", FakeTorch())

    backend = HFTransformersBackend(model="fake-model")
    result = backend.predict_sync({"text": "great"})

    assert result["label"] == "positive"
