from tactus.core.registry import RegistryBuilder


def test_register_context_validation_error_records():
    builder = RegistryBuilder()
    builder.register_context(123, {"policy": "bad"})
    assert builder.validation_messages


def test_register_corpus_maps_aliases():
    builder = RegistryBuilder()
    builder.register_corpus("corp", {"backend": "b1", "recipe": {"x": 1}})
    assert builder.registry.corpora["corp"].config["backend_id"] == "b1"
    assert builder.registry.corpora["corp"].config["recipe_config"] == {"x": 1}


def test_register_corpus_validation_error_records():
    builder = RegistryBuilder()
    builder.register_corpus(123, {"backend_id": 123})
    assert builder.validation_messages


def test_register_retriever_validation_error_records():
    builder = RegistryBuilder()
    builder.register_retriever(123, {"corpus": 123})
    assert builder.validation_messages


def test_register_compactor_validation_error_records():
    builder = RegistryBuilder()
    builder.register_compactor(123, {"strategy": 123})
    assert builder.validation_messages
