"""Tests for documentation extractor."""

from tactus.docs.extractor import TacFileExtractor, DirectoryExtractor


def test_extractor_parses_doc_blocks_and_params(tmp_path):
    tac_path = tmp_path / "sample.spec.tac"
    tac_path.write_text(
        """
--[[doc
## Overview
```lua
print('hello')
```
]]

--[[doc:parameter input
Input text.
Type: string
Required: false
Default: hi
]]

Specification([[\
Feature: Example
Scenario: Use it
Given a step
When another step
Then result
]])
""".strip(),
        encoding="utf-8",
    )

    extractor = TacFileExtractor(tac_path)
    doc_blocks = extractor.extract_doc_blocks()
    params = extractor.extract_parameter_docs()
    features = extractor.extract_bdd_features()
    examples = extractor.generate_code_examples(doc_blocks, features)

    assert len(doc_blocks) == 1
    assert "Overview" in doc_blocks[0].content

    assert len(params) == 1
    assert params[0].name == "input"
    assert params[0].type_hint == "string"
    assert params[0].required is False
    assert params[0].default == "hi"

    assert len(features) == 1
    assert features[0].name == "Example"
    assert features[0].scenarios[0].name == "Use it"

    assert any(example.source == "doc_block" for example in examples)
    assert any(example.source == "bdd_scenario" for example in examples)


def test_extractor_parameter_doc_without_metadata(tmp_path):
    tac_path = tmp_path / "sample.spec.tac"
    tac_path.write_text(
        """
--[[doc:parameter input
Just a description.
]]
""".strip(),
        encoding="utf-8",
    )

    extractor = TacFileExtractor(tac_path)
    params = extractor.extract_parameter_docs()

    assert params[0].type_hint is None
    assert params[0].required is True
    assert params[0].default is None


def test_extractor_skips_parameter_blocks_in_doc_blocks(tmp_path):
    tac_path = tmp_path / "sample.spec.tac"
    tac_path.write_text(
        """
--[[doc:parameter input
Input text.
]]

--[[doc
Regular docs.
]]
""".strip(),
        encoding="utf-8",
    )

    extractor = TacFileExtractor(tac_path)
    doc_blocks = extractor.extract_doc_blocks()

    assert len(doc_blocks) == 1
    assert "Regular docs." in doc_blocks[0].content


def test_extractor_skips_doc_blocks_with_parameter_prefix(tmp_path):
    tac_path = tmp_path / "sample.spec.tac"
    tac_path.write_text(
        """
--[[doc
:parameter ignored
]]
""".strip(),
        encoding="utf-8",
    )

    extractor = TacFileExtractor(tac_path)
    doc_blocks = extractor.extract_doc_blocks()

    assert doc_blocks == []


def test_extractor_handles_missing_feature(tmp_path):
    tac_path = tmp_path / "sample.spec.tac"
    tac_path.write_text(
        """
Specification([[\
Scenario: Missing feature
Given a step
]])
""".strip(),
        encoding="utf-8",
    )

    extractor = TacFileExtractor(tac_path)
    features = extractor.extract_bdd_features()

    assert features == []


def test_extractor_parses_feature_description_and_and_steps(tmp_path):
    tac_path = tmp_path / "sample.spec.tac"
    tac_path.write_text(
        """
Specification([[\
Short description line
Feature: Example
Scenario: Use it
Given a step
And another step
But not this
]])
""".strip(),
        encoding="utf-8",
    )

    extractor = TacFileExtractor(tac_path)
    features = extractor.extract_bdd_features()

    assert features[0].description == "Short description line"
    assert features[0].scenarios[0].steps[1].keyword == "And"
    assert features[0].scenarios[0].steps[2].keyword == "But"


def test_extractor_parses_feature_without_scenarios(tmp_path):
    tac_path = tmp_path / "sample.spec.tac"
    tac_path.write_text(
        """
Specification([[\
Feature: Example
]])
""".strip(),
        encoding="utf-8",
    )

    extractor = TacFileExtractor(tac_path)
    features = extractor.extract_bdd_features()

    assert features[0].scenarios == []


def test_extractor_ignores_blank_lines_in_gherkin(tmp_path):
    tac_path = tmp_path / "sample.spec.tac"
    tac_path.write_text(
        """
Specification([[
Feature: Example

Scenario: Blank lines
Given a step
]])
""".strip(),
        encoding="utf-8",
    )

    extractor = TacFileExtractor(tac_path)
    features = extractor.extract_bdd_features()

    assert features[0].scenarios[0].name == "Blank lines"


def test_extractor_ignores_non_keyword_lines_after_feature(tmp_path):
    tac_path = tmp_path / "sample.spec.tac"
    tac_path.write_text(
        """
Specification([[\
Feature: Example
Some freeform text
Scenario: Use it
Given a step
]])
""".strip(),
        encoding="utf-8",
    )

    extractor = TacFileExtractor(tac_path)
    features = extractor.extract_bdd_features()

    assert features[0].description is None


def test_extractor_parses_multiple_scenarios_and_steps(tmp_path):
    tac_path = tmp_path / "sample.spec.tac"
    tac_path.write_text(
        """
Specification([[\
Feature: Example
Scenario: First
Given a step
Scenario: Second
When another step
]])
""".strip(),
        encoding="utf-8",
    )

    extractor = TacFileExtractor(tac_path)
    features = extractor.extract_bdd_features()

    assert len(features[0].scenarios) == 2
    assert features[0].scenarios[0].name == "First"
    assert features[0].scenarios[1].steps[0].keyword == "When"


def test_extractor_parses_and_step_without_prior_keywords(tmp_path):
    tac_path = tmp_path / "sample.spec.tac"
    tac_path.write_text(
        """
Specification([[\
Feature: Example
Scenario: Only and
And a step
]])
""".strip(),
        encoding="utf-8",
    )

    extractor = TacFileExtractor(tac_path)
    features = extractor.extract_bdd_features()

    assert features[0].scenarios[0].steps[0].keyword == "And"


def test_extractor_parses_when_then_steps(tmp_path):
    tac_path = tmp_path / "sample.spec.tac"
    tac_path.write_text(
        """
Specification([[\
Feature: Example
Scenario: When then
When a step
Then a result
]])
""".strip(),
        encoding="utf-8",
    )

    extractor = TacFileExtractor(tac_path)
    features = extractor.extract_bdd_features()

    assert features[0].scenarios[0].steps[0].keyword == "When"
    assert features[0].scenarios[0].steps[1].keyword == "Then"


def test_generate_code_examples_uses_heading_title(tmp_path):
    tac_path = tmp_path / "sample.spec.tac"
    tac_path.write_text(
        """
--[[doc
## First Example
```lua
print("hi")
```
]]
""".strip(),
        encoding="utf-8",
    )

    extractor = TacFileExtractor(tac_path)
    doc_blocks = extractor.extract_doc_blocks()
    examples = extractor.generate_code_examples(doc_blocks, [])

    assert examples[0].title == "First Example"


def test_generate_code_examples_uses_default_title_without_heading(tmp_path):
    tac_path = tmp_path / "sample.spec.tac"
    tac_path.write_text(
        """
--[[doc
```lua
print("hi")
```
]]
""".strip(),
        encoding="utf-8",
    )

    extractor = TacFileExtractor(tac_path)
    doc_blocks = extractor.extract_doc_blocks()
    examples = extractor.generate_code_examples(doc_blocks, [])

    assert examples[0].title == "Example 1"


def test_extractor_module_doc_includes_index(tmp_path):
    module_dir = tmp_path / "classify"
    module_dir.mkdir()
    (module_dir / "index.md").write_text("Index content", encoding="utf-8")

    spec_path = tmp_path / "classify.spec.tac"
    spec_path.write_text("--[[doc\nDocs\n]]", encoding="utf-8")

    extractor = TacFileExtractor(spec_path)
    module_doc = extractor.extract_module_doc("classify", "tactus.classify", module_dir)

    assert module_doc.index_content == "Index content"
    assert module_doc.overview == "Docs"
    assert module_doc.has_specs is False


def test_extractor_module_doc_ignores_nonexistent_dir(tmp_path):
    spec_path = tmp_path / "classify.spec.tac"
    spec_path.write_text("--[[doc\nDocs\n]]", encoding="utf-8")

    extractor = TacFileExtractor(spec_path)
    module_doc = extractor.extract_module_doc("classify", "tactus.classify", tmp_path / "missing")

    assert module_doc.index_content is None


def test_directory_extractor_falls_back_to_module_parent(tmp_path):
    spec_dir = tmp_path / "modules"
    spec_dir.mkdir(parents=True)
    spec_path = spec_dir / "helper.spec.tac"
    spec_path.write_text("--[[doc\nDocs\n]]", encoding="utf-8")

    extractor = DirectoryExtractor(tmp_path)
    docs = extractor.extract_all()

    assert docs.modules[0].full_name == "helper"


def test_directory_extractor_falls_back_when_module_dir_missing(tmp_path):
    spec_dir = tmp_path / "tactus" / "stdlib"
    spec_dir.mkdir(parents=True)
    spec_path = spec_dir / "missing.spec.tac"
    spec_path.write_text("--[[doc\nDocs\n]]", encoding="utf-8")

    extractor = DirectoryExtractor(tmp_path)
    docs = extractor.extract_all()

    assert docs.modules[0].file_path.endswith("missing.spec.tac")


def test_directory_extractor_falls_back_when_module_dir_is_file(tmp_path):
    spec_dir = tmp_path / "tactus" / "stdlib"
    spec_dir.mkdir(parents=True)
    spec_path = spec_dir / "filelike.spec.tac"
    spec_path.write_text("--[[doc\nDocs\n]]", encoding="utf-8")
    (spec_dir / "filelike").write_text("not a directory", encoding="utf-8")

    extractor = DirectoryExtractor(tmp_path)
    docs = extractor.extract_all()

    assert docs.modules[0].full_name.endswith("filelike")


def test_directory_extractor_uses_module_dir_when_present(tmp_path):
    spec_dir = tmp_path / "tactus" / "stdlib"
    module_dir = spec_dir / "present"
    module_dir.mkdir(parents=True)
    spec_path = spec_dir / "present.spec.tac"
    spec_path.write_text("--[[doc\nDocs\n]]", encoding="utf-8")

    extractor = DirectoryExtractor(tmp_path)
    docs = extractor.extract_all()

    assert docs.modules[0].full_name.endswith("present")


def test_directory_extractor_builds_module_names(tmp_path):
    spec_dir = tmp_path / "stdlib" / "tac" / "tactus"
    spec_dir.mkdir(parents=True)
    spec_path = spec_dir / "classify.spec.tac"
    spec_path.write_text("--[[doc\nDocs\n]]", encoding="utf-8")

    extractor = DirectoryExtractor(tmp_path)
    docs = extractor.extract_all()

    assert docs.modules
    assert docs.modules[0].full_name == "tactus.classify"
