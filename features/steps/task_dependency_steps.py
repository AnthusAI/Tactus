"""
Steps for task dependency planning scenarios.
"""

import shutil
import tempfile
from pathlib import Path

from behave import given, then


@given("a NOAA corpus fixture copy")
def step_copy_noaa_corpus(context):
    fixture_root = Path("tests/fixtures/noaa_afd_corpus/MFL").resolve()
    if not fixture_root.exists():
        raise AssertionError(f"Fixture corpus not found: {fixture_root}")

    temp_dir = tempfile.mkdtemp(prefix="tactus_noaa_corpus_")
    corpus_root = Path(temp_dir) / "MFL"
    shutil.copytree(fixture_root, corpus_root, dirs_exist_ok=True)
    context.corpus_root = corpus_root


@given("an empty corpus workspace")
def step_empty_corpus_workspace(context):
    temp_dir = tempfile.mkdtemp(prefix="tactus_empty_corpus_")
    corpus_root = Path(temp_dir) / "MFL"
    corpus_root.mkdir(parents=True, exist_ok=True)
    context.corpus_root = corpus_root


@given("a task workflow that uses the copied corpus")
def step_write_dependency_workflow(context):
    if not hasattr(context, "corpus_root"):
        raise AssertionError("Corpus root not set for dependency workflow")

    workflow_source = f"""local FilesystemCorpus = require("tactus.corpora.filesystem")
local TfVector = require("tactus.retrievers.tf_vector")

miami_afd = FilesystemCorpus.Corpus {{
  root = "{context.corpus_root.as_posix()}"
}}

miami_search = TfVector.Retriever {{
  corpus = miami_afd,
  configuration = {{
    pipeline = {{
      query = {{
        limit = 1,
        maximum_total_characters = 2000
      }}
    }}
  }}
}}

Task "run" {{
  entry = function()
    return {{ status = "ok" }}
  end
}}
"""

    temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".tac", delete=False)
    temp_file.write(workflow_source)
    temp_file.close()
    context.lua_file = Path(temp_file.name)


@given("a task workflow with two retrievers")
def step_write_multi_retriever_workflow(context):
    if not hasattr(context, "corpus_root"):
        raise AssertionError("Corpus root not set for dependency workflow")

    workflow_source = f"""local FilesystemCorpus = require("tactus.corpora.filesystem")
local TfVector = require("tactus.retrievers.tf_vector")

miami_afd = FilesystemCorpus.Corpus {{
  root = "{context.corpus_root.as_posix()}"
}}

miami_search = TfVector.Retriever {{
  corpus = miami_afd,
  configuration = {{
    pipeline = {{
      query = {{
        limit = 1,
        maximum_total_characters = 2000
      }}
    }}
  }}
}}

miami_search_two = TfVector.Retriever {{
  corpus = miami_afd,
  configuration = {{
    pipeline = {{
      query = {{
        limit = 2,
        maximum_total_characters = 2000
      }}
    }}
  }}
}}
"""

    temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".tac", delete=False)
    temp_file.write(workflow_source)
    temp_file.close()
    context.lua_file = Path(temp_file.name)


@given("a task workflow with a load provider")
def step_write_load_provider_workflow(context):
    if not hasattr(context, "corpus_root"):
        raise AssertionError("Corpus root not set for dependency workflow")

    marker_path = (Path(context.corpus_root) / "loaded.txt").as_posix()
    workflow_source = f"""local FilesystemCorpus = require("tactus.corpora.filesystem")
local TfVector = require("tactus.retrievers.tf_vector")
local file = require("tactus.io.file")

miami_afd = FilesystemCorpus.Corpus {{
  root = "{context.corpus_root.as_posix()}"
}}

miami_search = TfVector.Retriever {{
  corpus = miami_afd,
  configuration = {{
    pipeline = {{
      query = {{
        limit = 1,
        maximum_total_characters = 2000
      }}
    }}
  }}
}}

Task "fetch" {{
  provides = {{ kind = "load", corpus = "miami_afd" }},
  entry = function()
    file.write("{marker_path}", "loaded")
    return {{ status = "loaded" }}
  end
}}

Task "run" {{
  entry = function()
    return {{ status = "ok" }}
  end
}}
"""

    temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".tac", delete=False)
    temp_file.write(workflow_source)
    temp_file.close()
    context.lua_file = Path(temp_file.name)


@given('I provide CLI input "{value}"')
def step_set_cli_input(context, value):
    context.cli_input = f"{value}\n"


@then("an extraction snapshot should exist")
def step_assert_extraction_snapshot(context):
    corpus_root = Path(context.corpus_root)
    snapshots_root = corpus_root / ".biblicus" / "snapshots" / "extraction"
    if not snapshots_root.exists():
        raise AssertionError("Extraction snapshots directory missing")

    manifests = list(snapshots_root.glob("**/manifest.json"))
    assert manifests, "No extraction snapshot manifests found"


@then("a retrieval snapshot should exist")
def step_assert_retrieval_snapshot(context):
    corpus_root = Path(context.corpus_root)
    snapshots_root = corpus_root / ".biblicus" / "snapshots"
    if not snapshots_root.exists():
        raise AssertionError("Snapshots directory missing")

    snapshot_files = [path for path in snapshots_root.glob("*.json") if path.is_file()]
    assert snapshot_files, "No retrieval snapshot manifests found"


@then("at least {count:d} retrieval snapshots should exist")
def step_assert_retrieval_snapshot_count(context, count):
    corpus_root = Path(context.corpus_root)
    snapshots_root = corpus_root / ".biblicus" / "snapshots"
    if not snapshots_root.exists():
        raise AssertionError("Snapshots directory missing")

    snapshot_files = [path for path in snapshots_root.glob("*.json") if path.is_file()]
    assert (
        len(snapshot_files) >= count
    ), f"Expected at least {count} retrieval snapshots, found {len(snapshot_files)}"


@then("the load marker should exist")
def step_assert_load_marker(context):
    marker_path = Path(context.corpus_root) / "loaded.txt"
    assert marker_path.exists(), f"Load marker not found: {marker_path}"
