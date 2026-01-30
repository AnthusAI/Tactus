"""
Extract documentation from Tactus .tac files.

This module parses .tac files to extract:
- --[[doc]] comment blocks (Markdown documentation)
- --[[doc:parameter name]] blocks (Parameter documentation)
- Specification([[...]]) blocks (BDD specifications in Gherkin format)
"""

import re
from pathlib import Path
from typing import List, Optional
from tactus.docs.models import (
    DocBlock,
    ParameterDoc,
    BDDStep,
    BDDScenario,
    BDDFeature,
    CodeExample,
    ModuleDoc,
    DocumentationTree,
)


class TacFileExtractor:
    """Extract documentation from a single .tac file."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.content = file_path.read_text()
        self.lines = self.content.split("\n")

    def extract_doc_blocks(self) -> List[DocBlock]:
        """
        Extract --[[doc]] and --[[doc:parameter]] blocks.

        Returns regular doc blocks (parameter blocks handled separately).
        """
        doc_blocks = []
        pattern = r"--\[\[doc\s*\n(.*?)\]\]"

        for match in re.finditer(pattern, self.content, re.DOTALL):
            content = match.group(1)
            # Skip parameter docs (handled separately)
            if content.strip().startswith(":parameter"):
                continue

            # Find line number
            line_num = self.content[: match.start()].count("\n") + 1

            doc_blocks.append(DocBlock(content=content.strip(), line_number=line_num))

        return doc_blocks

    def extract_parameter_docs(self) -> List[ParameterDoc]:
        """
        Extract --[[doc:parameter name]] blocks.

        Format:
        --[[doc:parameter <name>
        Description here.
        Type: string (optional)
        Required: true/false (optional)
        Default: value (optional)
        ]]
        """
        parameter_docs = []
        pattern = r"--\[\[doc:parameter\s+(\w+)\s*\n(.*?)\]\]"

        for match in re.finditer(pattern, self.content, re.DOTALL):
            param_name = match.group(1)
            content = match.group(2).strip()

            # Parse optional metadata
            type_hint = None
            required = True
            default = None

            # Extract type if present
            type_match = re.search(r"Type:\s*(\S+)", content)
            if type_match:
                type_hint = type_match.group(1)
                content = re.sub(r"Type:\s*\S+\s*\n?", "", content)

            # Extract required if present
            required_match = re.search(r"Required:\s*(true|false)", content, re.IGNORECASE)
            if required_match:
                required = required_match.group(1).lower() == "true"
                content = re.sub(
                    r"Required:\s*(?:true|false)\s*\n?", "", content, flags=re.IGNORECASE
                )

            # Extract default if present
            default_match = re.search(r"Default:\s*(.+)", content)
            if default_match:
                default = default_match.group(1).strip()
                content = re.sub(r"Default:\s*.+\s*\n?", "", content)

            parameter_docs.append(
                ParameterDoc(
                    name=param_name,
                    description=content.strip(),
                    type_hint=type_hint,
                    required=required,
                    default=default,
                )
            )

        return parameter_docs

    def extract_bdd_features(self) -> List[BDDFeature]:
        """
        Extract BDD features from Specification([[ ... ]]) blocks.

        Parses Gherkin syntax:
        Feature: Name
          Scenario: Name
            Given step
            When step
            Then step
        """
        features = []
        pattern = r"Specification\(\[\[(.*?)\]\]\)"

        for match in re.finditer(pattern, self.content, re.DOTALL):
            gherkin_content = match.group(1).strip()
            line_num = self.content[: match.start()].count("\n") + 1

            feature = self._parse_gherkin(gherkin_content, line_num)
            if feature:
                features.append(feature)

        return features

    def _parse_gherkin(self, gherkin: str, start_line: int) -> Optional[BDDFeature]:
        """Parse Gherkin syntax into BDDFeature."""
        lines = gherkin.split("\n")

        # Extract feature name and description
        feature_name = None
        feature_desc_lines = []
        scenarios = []
        current_scenario = None
        current_steps = []

        for line in lines:
            line = line.strip()

            if not line:
                continue

            if line.startswith("Feature:"):
                feature_name = line[8:].strip()

            elif line.startswith("Scenario:"):
                # Save previous scenario if exists
                if current_scenario:
                    scenarios.append(
                        BDDScenario(
                            name=current_scenario,
                            steps=current_steps,
                            line_number=start_line,  # Approximate
                        )
                    )

                current_scenario = line[9:].strip()
                current_steps = []

            else:
                for keyword in ["Given", "When", "Then", "And", "But"]:
                    if line.startswith(keyword + " "):
                        step_text = line[len(keyword) + 1 :].strip()
                        current_steps.append(BDDStep(keyword=keyword, text=step_text))
                        break
                else:
                    if not feature_name:
                        feature_desc_lines.append(line)

        # Save last scenario
        if current_scenario:
            scenarios.append(
                BDDScenario(
                    name=current_scenario,
                    steps=current_steps,
                    line_number=start_line,
                )
            )

        if not feature_name:
            return None

        feature_desc = "\n".join(feature_desc_lines).strip() if feature_desc_lines else None

        return BDDFeature(
            name=feature_name,
            description=feature_desc,
            scenarios=scenarios,
            line_number=start_line,
        )

    def generate_code_examples(
        self, doc_blocks: List[DocBlock], features: List[BDDFeature]
    ) -> List[CodeExample]:
        """
        Generate code examples from doc blocks and BDD scenarios.

        Extracts ```lua code blocks from doc blocks and generates
        examples from BDD scenarios.
        """
        examples = []

        # Extract code blocks from doc blocks
        for doc_block in doc_blocks:
            code_blocks = re.findall(r"```lua\n(.*?)\n```", doc_block.content, re.DOTALL)
            for idx, code in enumerate(code_blocks):
                # Try to extract title from heading before code block
                title = f"Example {idx + 1}"
                heading_match = re.search(r"##\s+(.+?)\n```lua", doc_block.content, re.DOTALL)
                if heading_match:
                    title = heading_match.group(1).strip()

                examples.append(
                    CodeExample(
                        title=title,
                        code=code.strip(),
                        description=None,
                        source="doc_block",
                    )
                )

        # Generate examples from BDD scenarios
        for feature in features:
            for scenario in feature.scenarios:
                code_lines = [f"-- Scenario: {scenario.name}"]
                for step in scenario.steps:
                    code_lines.append(f"-- {step.keyword} {step.text}")

                examples.append(
                    CodeExample(
                        title=scenario.name,
                        code="\n".join(code_lines),
                        description=f"From feature: {feature.name}",
                        source="bdd_scenario",
                    )
                )

        return examples

    def extract_module_doc(
        self, module_name: str, full_module_name: str, module_dir: Optional[Path] = None
    ) -> ModuleDoc:
        """Extract complete documentation for this module."""
        doc_blocks = self.extract_doc_blocks()
        parameter_docs = self.extract_parameter_docs()
        features = self.extract_bdd_features()
        examples = self.generate_code_examples(doc_blocks, features)

        # Use first doc block as overview
        overview = doc_blocks[0].content if doc_blocks else None

        # Look for index.md in module directory
        index_content = None
        if module_dir and module_dir.is_dir():
            index_md = module_dir / "index.md"
            if index_md.exists():
                index_content = index_md.read_text()

        return ModuleDoc(
            name=module_name,
            full_name=full_module_name,
            file_path=str(self.file_path),
            doc_blocks=doc_blocks,
            overview=overview,
            index_content=index_content,
            parameters=parameter_docs,
            features=features,
            examples=examples,
            line_count=len(self.lines),
            has_specs=len(features) > 0,
        )


class DirectoryExtractor:
    """Extract documentation from all .tac files in a directory."""

    def __init__(self, root_path: Path):
        self.root_path = root_path

    def extract_all(self) -> DocumentationTree:
        """Extract documentation from all .tac files."""
        modules = []

        # Find all .spec.tac files
        for spec_file in self.root_path.rglob("*.spec.tac"):
            # Derive module name from file path
            # e.g., tactus/stdlib/tac/tactus/classify.spec.tac -> tactus.classify
            relative = spec_file.relative_to(self.root_path)
            parts = relative.parts

            # Remove .spec.tac extension
            module_name = spec_file.stem.replace(".spec", "")

            # Build full module name from path
            # If path is tactus/stdlib/tac/tactus/classify.spec.tac
            # -> tactus.classify
            if "tactus" in parts:
                # Find first "tactus" and build from there
                tactus_idx = parts.index("tactus")
                module_parts = list(parts[tactus_idx:-1]) + [module_name]
                full_module_name = ".".join(module_parts)
            else:
                full_module_name = module_name

            # Find module directory (parent of spec file or sibling directory)
            # For tactus/stdlib/tac/tactus/classify.spec.tac
            # -> look for tactus/stdlib/tac/tactus/classify/ directory
            module_dir = spec_file.parent / module_name
            if not module_dir.is_dir():
                # Fallback: spec file's parent is the module directory
                module_dir = spec_file.parent

            # Extract documentation
            extractor = TacFileExtractor(spec_file)
            module_doc = extractor.extract_module_doc(module_name, full_module_name, module_dir)
            modules.append(module_doc)

        return DocumentationTree(root_path=str(self.root_path), modules=modules)
