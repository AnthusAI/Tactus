#!/usr/bin/env python3
"""
Audit script to identify which example files need mock configurations.

This script analyzes all .tac files in the examples/ directory and reports:
- Which have Specifications blocks
- Which have Mocks {} blocks
- What mockable entities they use (Agents, Modules, Tools)
- Mock coverage percentage
"""

import re
from pathlib import Path
from typing import List, Set
from dataclasses import dataclass


@dataclass
class ExampleAnalysis:
    """Analysis result for a single example file."""

    filename: str
    has_specs: bool
    has_mocks: bool
    agents: Set[str]
    modules: Set[str]
    tools: Set[str]
    mocked_entities: Set[str]

    @property
    def total_entities(self) -> int:
        """Total number of mockable entities."""
        return len(self.agents) + len(self.modules) + len(self.tools)

    @property
    def coverage_pct(self) -> float:
        """Percentage of entities that are mocked."""
        if self.total_entities == 0:
            return 100.0 if self.has_mocks else 0.0
        return (len(self.mocked_entities) / self.total_entities) * 100

    @property
    def status(self) -> str:
        """Status indicator for this example."""
        if not self.has_specs:
            return "⚠️ NO SPECS"
        if self.total_entities == 0:
            return "✅ NO DEPS"  # No external dependencies
        if not self.has_mocks:
            return "❌ NEEDS MOCKS"
        if self.coverage_pct < 100:
            return "⚠️ PARTIAL"
        return "✅ OK"


def analyze_example(file_path: Path) -> ExampleAnalysis:
    """Analyze a single example file."""
    content = file_path.read_text()

    # Check for specifications
    has_specs = bool(re.search(r"Specifications\s*\(\[", content))

    # Check for mocks block
    has_mocks = bool(re.search(r"Mocks\s*\{", content))

    # Find agents (Agent "name" or Agent {)
    agents = set()
    for match in re.finditer(r'Agent\s+"([^"]+)"', content):
        agents.add(match.group(1))
    for match in re.finditer(r"Agent\s*\{", content):
        # Try to find name in the block
        # This is a heuristic - may need refinement
        pass

    # Find modules (Module "name" {)
    modules = set()
    for match in re.finditer(r'Module\s+"([^"]+)"\s*\{', content):
        modules.add(match.group(1))
    for match in re.finditer(r'local\s+\w+\s*=\s*Module\s+"([^"]+)"', content):
        modules.add(match.group(1))

    # Find tools (Tool("name") or direct function calls)
    tools = set()
    for match in re.finditer(r'Tool\s*\(\s*"([^"]+)"\s*\)', content):
        tools.add(match.group(1))

    # Find mocked entities in Mocks {} block
    mocked_entities = set()
    if has_mocks:
        # Extract the Mocks {} block
        mocks_match = re.search(r"Mocks\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}", content, re.DOTALL)
        if mocks_match:
            mocks_content = mocks_match.group(1)
            # Find all top-level keys in the mocks block
            for match in re.finditer(r"^\s*(\w+)\s*=\s*\{", mocks_content, re.MULTILINE):
                mocked_entities.add(match.group(1))

    return ExampleAnalysis(
        filename=file_path.stem,
        has_specs=has_specs,
        has_mocks=has_mocks,
        agents=agents,
        modules=modules,
        tools=tools,
        mocked_entities=mocked_entities,
    )


def generate_report(analyses: List[ExampleAnalysis]) -> str:
    """Generate a markdown report from analyses."""
    # Sort by status (problems first) then by name
    status_priority = {
        "❌ NEEDS MOCKS": 0,
        "⚠️ PARTIAL": 1,
        "⚠️ NO SPECS": 2,
        "✅ OK": 3,
        "✅ NO DEPS": 4,
    }
    analyses_sorted = sorted(
        analyses, key=lambda a: (status_priority.get(a.status, 99), a.filename)
    )

    report = []
    report.append("# Example Mocking Audit Report\n")
    report.append(f"Total examples analyzed: {len(analyses)}\n")

    # Summary statistics
    with_specs = sum(1 for a in analyses if a.has_specs)
    with_mocks = sum(1 for a in analyses if a.has_mocks)
    needs_mocks = sum(1 for a in analyses if a.status == "❌ NEEDS MOCKS")
    partial_mocks = sum(1 for a in analyses if a.status == "⚠️ PARTIAL")

    report.append("\n## Summary\n")
    report.append(f"- ✅ With specs: {with_specs}/{len(analyses)}\n")
    report.append(f"- ✅ With mocks: {with_mocks}/{len(analyses)}\n")
    report.append(f"- ❌ Need mocks: {needs_mocks}\n")
    report.append(f"- ⚠️ Partial mocks: {partial_mocks}\n")

    # Detailed table
    report.append("\n## Detailed Analysis\n")
    report.append(
        "| Example | Specs | Mocks | Agents | Modules | Tools | Mocked | Coverage | Status |\n"
    )
    report.append(
        "|---------|-------|-------|--------|---------|-------|--------|----------|--------|\n"
    )

    for analysis in analyses_sorted:
        specs_icon = "✅" if analysis.has_specs else "❌"
        mocks_icon = "✅" if analysis.has_mocks else "❌"

        report.append(
            f"| {analysis.filename} | {specs_icon} | {mocks_icon} | "
            f"{len(analysis.agents)} | {len(analysis.modules)} | {len(analysis.tools)} | "
            f"{len(analysis.mocked_entities)} | {analysis.coverage_pct:.0f}% | "
            f"{analysis.status} |\n"
        )

    # Examples needing attention
    needs_attention = [
        a for a in analyses if a.status in ["❌ NEEDS MOCKS", "⚠️ PARTIAL", "⚠️ NO SPECS"]
    ]
    if needs_attention:
        report.append(f"\n## Examples Needing Attention ({len(needs_attention)})\n")
        for analysis in needs_attention:
            report.append(f"\n### {analysis.filename} - {analysis.status}\n")
            if not analysis.has_specs:
                report.append("- **Missing specifications block**\n")
            if not analysis.has_mocks and analysis.total_entities > 0:
                report.append("- **Missing Mocks {} block**\n")
            if analysis.agents:
                report.append(f"- Agents: {', '.join(sorted(analysis.agents))}\n")
            if analysis.modules:
                report.append(f"- Modules: {', '.join(sorted(analysis.modules))}\n")
            if analysis.tools:
                report.append(f"- Tools: {', '.join(sorted(analysis.tools))}\n")
            if analysis.mocked_entities:
                report.append(f"- Mocked: {', '.join(sorted(analysis.mocked_entities))}\n")

            # Show what's missing
            all_entities = analysis.agents | analysis.modules | analysis.tools
            unmocked = all_entities - analysis.mocked_entities
            if unmocked:
                report.append(f"- **Unmocked entities**: {', '.join(sorted(unmocked))}\n")

    return "".join(report)


def main():
    """Main entry point."""
    examples_dir = Path(__file__).parent.parent / "examples"

    if not examples_dir.exists():
        print(f"Error: Examples directory not found: {examples_dir}")
        return 1

    # Find all .tac files
    tac_files = sorted(examples_dir.glob("*.tac"))

    if not tac_files:
        print(f"Error: No .tac files found in {examples_dir}")
        return 1

    print(f"Analyzing {len(tac_files)} example files...")

    # Analyze each file
    analyses = []
    for tac_file in tac_files:
        try:
            analysis = analyze_example(tac_file)
            analyses.append(analysis)
        except Exception as e:
            print(f"Error analyzing {tac_file.name}: {e}")

    # Generate report
    report = generate_report(analyses)

    # Write report to file
    report_path = Path(__file__).parent.parent / "MOCKING_AUDIT.md"
    report_path.write_text(report)

    print(f"\nReport written to: {report_path}")
    print(report)

    return 0


if __name__ == "__main__":
    exit(main())
