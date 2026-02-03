import pytest

from tactus.core.dsl_stubs import (
    _normalize_context_pack_entry,
    _normalize_handle_name,
    _normalize_template_vars,
    create_dsl_stubs,
)
from tactus.core.registry import RegistryBuilder
from tactus.primitives.handles import (
    CompactorHandle,
    ContextHandle,
    CorpusHandle,
    RetrieverHandle,
)


def test_template_directive_and_message_helpers():
    stubs = create_dsl_stubs(RegistryBuilder())

    directive = stubs["template"]("Hello {input.name}", [])
    assert directive == {"template": "Hello {input.name}", "vars": {}}

    directive_empty_vars = stubs["template"]("Hello {input.name}", [])
    assert directive_empty_vars["vars"] == {}

    assert stubs["system"](directive)["template"] == "Hello {input.name}"
    assert stubs["user"]("hi") == {"type": "user", "content": "hi"}
    assert stubs["assistant"]("ok") == {"type": "assistant", "content": "ok"}

    with pytest.raises(TypeError):
        stubs["template"](123)
    with pytest.raises(TypeError):
        stubs["system"](123)


def test_template_directive_with_empty_lua_table():
    stubs = create_dsl_stubs(RegistryBuilder())

    class EmptyLuaTable:
        def keys(self):
            return []

        def items(self):
            return []

    directive = stubs["template"]("Hello {input.name}", EmptyLuaTable())
    assert directive["vars"] == {}


def test_template_directive_with_monkeypatched_empty_vars(monkeypatch):
    import tactus.core.dsl_stubs as dsl_stubs

    monkeypatch.setattr(dsl_stubs, "lua_table_to_dict", lambda _value: [])
    stubs = create_dsl_stubs(RegistryBuilder())
    directive = stubs["template"]("Hello {input.name}", {"a": 1})
    assert directive["vars"] == {}


def test_template_directive_with_monkeypatched_empty_vars_again(monkeypatch):
    import tactus.core.dsl_stubs as dsl_stubs

    monkeypatch.setattr(dsl_stubs, "lua_table_to_dict", lambda _value: [])
    stubs = create_dsl_stubs(RegistryBuilder())
    directive = stubs["template"]("Hello {input.name}", {"b": 2})
    assert directive["vars"] == {}


def test_template_directive_with_list_vars_table(monkeypatch):
    import tactus.core.dsl_stubs as dsl_stubs

    monkeypatch.setattr(dsl_stubs, "lua_table_to_dict", lambda value: value)
    stubs = create_dsl_stubs(RegistryBuilder())
    directive = stubs["template"]("Hello {input.name}", [])
    assert directive["vars"] == {}


def test_template_directive_empty_list_branch(monkeypatch):
    import tactus.core.dsl_stubs as dsl_stubs

    monkeypatch.setattr(dsl_stubs, "lua_table_to_dict", lambda _value: [])
    stubs = create_dsl_stubs(RegistryBuilder())
    directive = stubs["template"]("Hello {input.name}", {"c": 3})
    assert directive["vars"] == {}


def test_normalize_handle_name_handles_objects():
    class Named:
        name = "value"

    assert _normalize_handle_name(Named()) == "value"
    assert _normalize_handle_name("raw") == "raw"


def test_normalize_template_vars_handles_empty_list():
    assert _normalize_template_vars([]) == {}
    assert _normalize_template_vars({"a": 1}) == {"a": 1}


def test_context_insert_directive():
    stubs = create_dsl_stubs(RegistryBuilder())
    directive = stubs["context"]("pack", [])
    assert directive == {"type": "context", "name": "pack"}
    with pytest.raises(TypeError):
        stubs["context"](123)

    class Pack:
        name = "named"

    directive = stubs["context"](Pack(), {"max_tokens": 1})
    assert directive == {"type": "context", "name": "named", "budget": {"max_tokens": 1}}

    assert stubs["history"]() == {"type": "history"}


def test_new_context_normalizes_packs_and_compactor():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)
    compactor = CompactorHandle("compactor")
    pack = RetrieverHandle("pack")

    ctx = stubs["Context"]({"name": "support", "packs": [pack], "policy": {"compactor": compactor}})

    declaration = builder.registry.contexts[ctx.name]
    assert declaration.name == "support"
    assert declaration.packs[0].name == "pack"
    assert declaration.policy.compactor == "compactor"


def test_new_context_normalizes_pack_dict_and_empty_list():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)
    pack = RetrieverHandle("pack")

    ctx = stubs["Context"]({"name": "support", "packs": {"name": pack}})
    declaration = builder.registry.contexts[ctx.name]
    assert declaration.packs[0].name == "pack"

    ctx_empty = stubs["Context"]([])
    assert ctx_empty.name in builder.registry.contexts


def test_new_context_wraps_single_pack():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)
    pack = RetrieverHandle("pack")

    ctx = stubs["Context"]({"packs": pack})
    declaration = builder.registry.contexts[ctx.name]
    assert declaration.packs[0].name == "pack"


def test_new_context_normalizes_pack_name_string():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    ctx = stubs["Context"]({"packs": [{"name": "pack"}]})
    declaration = builder.registry.contexts[ctx.name]
    assert declaration.packs[0].name == "pack"


def test_new_context_normalizes_pack_name_handle():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)
    pack = RetrieverHandle("pack")

    ctx = stubs["Context"]({"packs": [{"name": pack}]})
    declaration = builder.registry.contexts[ctx.name]
    assert declaration.packs[0].name == "pack"


def test_new_context_normalizes_pack_entry_dict_with_name_handle():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)
    pack = RetrieverHandle("pack")

    ctx = stubs["Context"]({"packs": {"name": pack}})
    declaration = builder.registry.contexts[ctx.name]
    assert declaration.packs[0].name == "pack"


def test_new_context_normalizes_pack_entry_with_name_via_monkeypatch(monkeypatch):
    import tactus.core.dsl_stubs as dsl_stubs

    monkeypatch.setattr(
        dsl_stubs,
        "lua_table_to_dict",
        lambda _value: {"packs": [{"name": "pack"}]},
    )
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)
    ctx = stubs["Context"]({"ignored": True})
    declaration = builder.registry.contexts[ctx.name]
    assert declaration.packs[0].name == "pack"


def test_normalize_context_pack_entry_branches():
    class Named:
        name = "pack"

    assert _normalize_context_pack_entry(Named()) == {"name": "pack"}
    assert _normalize_context_pack_entry({"name": Named()}) == {"name": "pack"}
    assert _normalize_context_pack_entry({"budget": {"max_tokens": 1}}) == {
        "budget": {"max_tokens": 1}
    }


def test_new_context_leaves_compactor_without_name():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    ctx = stubs["Context"]({"policy": {"compactor": "compact"}})
    declaration = builder.registry.contexts[ctx.name]
    assert declaration.policy.compactor == "compact"


def test_new_context_accepts_empty_tuple_config():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)
    ctx = stubs["Context"](())
    assert ctx.name in builder.registry.contexts


def test_new_context_requires_config():
    stubs = create_dsl_stubs(RegistryBuilder())
    with pytest.raises(TypeError):
        stubs["Context"]("bad")
    with pytest.raises(TypeError):
        stubs["Context"]()


def test_new_context_validates_name():
    stubs = create_dsl_stubs(RegistryBuilder())
    with pytest.raises(TypeError):
        stubs["Context"]({"name": 123})
    with pytest.raises(TypeError):
        stubs["Context"]({"name": " "})


def test_new_corpus_validates_and_maps_fields():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    corpus = stubs["_tactus_internal_corpus"](
        {"name": "docs", "root": "/tmp", "configuration": {"pipeline": {}}}
    )
    declaration = builder.registry.corpora[corpus.name]
    assert declaration.config["corpus_root"] == "/tmp"
    assert declaration.config["configuration"] == {"pipeline": {}}

    with pytest.raises(TypeError):
        stubs["_tactus_internal_corpus"]("bad")
    with pytest.raises(TypeError):
        stubs["_tactus_internal_corpus"]()
    with pytest.raises(TypeError):
        stubs["_tactus_internal_corpus"]({"name": 123})
    with pytest.raises(TypeError):
        stubs["_tactus_internal_corpus"]({"name": " "})

    empty_corpus = stubs["_tactus_internal_corpus"]([])
    assert empty_corpus.name in builder.registry.corpora


def test_new_corpus_accepts_named_config():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)
    corpus = stubs["_tactus_internal_corpus"]({"name": "docs"})
    assert corpus.name == "docs"
    assert "docs" in builder.registry.corpora


def test_new_corpus_accepts_empty_tuple_config():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)
    corpus = stubs["_tactus_internal_corpus"](())
    assert corpus.name in builder.registry.corpora


def test_new_retriever_validates_and_normalizes_corpus_handle():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)
    corpus = CorpusHandle("docs")
    retriever = stubs["_tactus_internal_retriever"]({"name": "search", "corpus": corpus})

    declaration = builder.registry.retrievers[retriever.name]
    assert declaration.corpus == "docs"

    with pytest.raises(TypeError):
        stubs["_tactus_internal_retriever"]("bad")
    with pytest.raises(TypeError):
        stubs["_tactus_internal_retriever"]()
    with pytest.raises(TypeError):
        stubs["_tactus_internal_retriever"]({"name": 123})
    with pytest.raises(TypeError):
        stubs["_tactus_internal_retriever"]({"name": " "})

    empty_retriever = stubs["_tactus_internal_retriever"]([])
    assert empty_retriever.name in builder.registry.retrievers


def test_new_retriever_accepts_named_config():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)
    retriever = stubs["_tactus_internal_retriever"]({"name": "search", "corpus": "docs"})
    assert retriever.name == "search"
    assert "search" in builder.registry.retrievers


def test_new_retriever_accepts_empty_tuple_config():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)
    retriever = stubs["_tactus_internal_retriever"](())
    assert retriever.name in builder.registry.retrievers


def test_new_compactor_registers_named_compactor():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)
    compactor = stubs["Compactor"]({"name": "compact"})
    assert compactor.name == "compact"
    assert "compact" in builder.registry.compactors


def test_new_compactor_accepts_empty_tuple_config():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)
    compactor = stubs["Compactor"](())
    assert compactor.name in builder.registry.compactors


def test_new_compactor_validates_name():
    stubs = create_dsl_stubs(RegistryBuilder())
    with pytest.raises(TypeError):
        stubs["Compactor"]("bad")
    with pytest.raises(TypeError):
        stubs["Compactor"]()
    with pytest.raises(TypeError):
        stubs["Compactor"]({"name": 123})
    with pytest.raises(TypeError):
        stubs["Compactor"]({"name": " "})

    compactor = stubs["Compactor"]([])
    assert compactor.name.startswith("_temp_compactor_")


def test_agent_context_handle_normalized_in_curried_config():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)
    context = ContextHandle("support")

    agent_factory = stubs["Agent"]("agent")
    agent_factory({"context": context, "system_prompt": "hi"})

    declaration = builder.registry.agents["agent"]
    assert declaration.model_extra["context"] == "support"


def test_agent_context_string_in_curried_config():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    agent_factory = stubs["Agent"]("agent")
    agent_factory({"context": "support", "system_prompt": "hi"})

    declaration = builder.registry.agents["agent"]
    assert declaration.model_extra["context"] == "support"


def test_agent_session_alias_rejected_in_curried_config():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)
    agent_factory = stubs["Agent"]("agent")
    with pytest.raises(ValueError):
        agent_factory({"session": {"source": "own"}})


def test_agent_context_handle_normalized_in_assignment_config():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)
    context = ContextHandle("support")

    agent = stubs["Agent"]({"context": context, "system_prompt": "hi"})

    declaration = builder.registry.agents[agent.name]
    assert declaration.model_extra["context"] == "support"


def test_agent_context_string_in_assignment_config():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    agent = stubs["Agent"]({"context": "support", "system_prompt": "hi"})

    declaration = builder.registry.agents[agent.name]
    assert declaration.model_extra["context"] == "support"


def test_binding_callback_renames_context_corpus_retriever_compactor():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)
    callback = stubs["_tactus_register_binding"]
    context_registry = stubs["_registries"]["context"]
    corpus_registry = stubs["_registries"]["corpus"]
    retriever_registry = stubs["_registries"]["retriever"]
    compactor_registry = stubs["_registries"]["compactor"]

    context = ContextHandle("_temp_context_123")
    context_registry[context.name] = context
    builder.registry.contexts[context.name] = object()
    callback("ctx", context)
    assert context.name == "ctx"

    corpus = CorpusHandle("_temp_corpus_123")
    corpus_registry[corpus.name] = corpus
    builder.registry.corpora[corpus.name] = object()
    callback("corp", corpus)
    assert corpus.name == "corp"

    retriever = RetrieverHandle("_temp_retriever_123")
    retriever_registry[retriever.name] = retriever
    builder.registry.retrievers[retriever.name] = object()
    callback("ret", retriever)
    assert retriever.name == "ret"

    compactor = CompactorHandle("_temp_compactor_123")
    compactor_registry[compactor.name] = compactor
    builder.registry.compactors[compactor.name] = object()
    callback("comp", compactor)
    assert compactor.name == "comp"

    with pytest.raises(RuntimeError):
        callback("wrong", ContextHandle("explicit"))


def test_binding_callback_mismatch_for_corpus_retriever_compactor():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)
    callback = stubs["_tactus_register_binding"]

    with pytest.raises(RuntimeError):
        callback("corp", CorpusHandle("explicit"))
    with pytest.raises(RuntimeError):
        callback("ret", RetrieverHandle("explicit"))
    with pytest.raises(RuntimeError):
        callback("comp", CompactorHandle("explicit"))


def test_binding_callback_mismatch_for_context():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)
    callback = stubs["_tactus_register_binding"]

    with pytest.raises(RuntimeError):
        callback("ctx", ContextHandle("explicit"))


def test_binding_callback_allows_matching_explicit_names():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)
    callback = stubs["_tactus_register_binding"]

    context = ContextHandle("ctx")
    callback("ctx", context)
    assert context.name == "ctx"

    corpus = CorpusHandle("corp")
    callback("corp", corpus)
    assert corpus.name == "corp"

    retriever = RetrieverHandle("ret")
    callback("ret", retriever)
    assert retriever.name == "ret"

    compactor = CompactorHandle("comp")
    callback("comp", compactor)
    assert compactor.name == "comp"


def test_binding_callback_temp_handles_without_registry_entries():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)
    callback = stubs["_tactus_register_binding"]

    context = ContextHandle("_temp_context_abc")
    callback("ctx", context)
    assert context.name == "ctx"

    corpus = CorpusHandle("_temp_corpus_abc")
    callback("corp", corpus)
    assert corpus.name == "corp"

    retriever = RetrieverHandle("_temp_retriever_abc")
    callback("ret", retriever)
    assert retriever.name == "ret"

    compactor = CompactorHandle("_temp_compactor_abc")
    callback("comp", compactor)
    assert compactor.name == "comp"
