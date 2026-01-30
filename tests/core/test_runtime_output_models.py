from tactus.core.runtime import TactusRuntime


class DummyField:
    def __init__(self, type_value, required=True):
        self.type = type_value
        self.required = required


class DummySchema:
    def __init__(self, fields):
        self.fields = fields


def test_map_type_string_variants():
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())

    assert runtime._map_type_string("string") is str
    assert runtime._map_type_string("INT") is int
    assert runtime._map_type_string("bool") is bool
    assert runtime._map_type_string("array") is list
    assert runtime._map_type_string("object") is dict
    assert runtime._map_type_string("unknown") is str


def test_create_pydantic_model_from_output_dict():
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())

    model = runtime._create_pydantic_model_from_output(
        {
            "name": {"type": "string", "required": True},
            "age": {"type": "integer", "required": False},
        },
        model_name="Out",
    )

    fields = model.model_fields
    assert fields["name"].is_required()
    assert fields["age"].is_required() is False


def test_create_pydantic_model_from_output_object():
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())

    schema = DummySchema({"flag": DummyField("boolean", required=True)})
    model = runtime._create_pydantic_model_from_output(schema, model_name="OutObj")

    fields = model.model_fields
    assert fields["flag"].is_required()


def test_create_output_model_from_schema():
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())

    model = runtime._create_output_model_from_schema(
        {
            "score": {"type": "number", "required": True, "description": "a"},
            "label": {"type": "string", "required": False},
        }
    )

    fields = model.model_fields
    assert fields["score"].is_required()
    assert fields["label"].is_required() is False
