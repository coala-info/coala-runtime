#!/usr/bin/env python3
"""
Test script to verify MCP server tools work correctly with test examples.
This script simulates MCP tool calls by importing and calling the server functions directly.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from coala_runtime.server import (
    coala_python_executor,
    coala_r_executor,
    PythonExecutorInput,
    RExecutorInput,
)


async def test_python_boxplot():
    """Test the Python boxplot example via MCP tool."""
    print("=" * 60)
    print("Testing Python Boxplot via MCP Tool")
    print("=" * 60)

    script_path = Path(__file__).parent / "scripts/boxplot_script.py"
    script_content = script_path.read_text()

    # Create input model (simulating MCP tool call)
    params = PythonExecutorInput(
        script=script_content,
        packages=[],
        input_files={},
        timeout=300,
    )

    result = await coala_python_executor(params)

    print(f"Success: {result.success}")
    print(f"Exit code: {result.exit_code}")
    print(f"\nStdout:\n{result.stdout}")
    if result.stderr:
        print(f"\nStderr:\n{result.stderr[:500]}")
    print(f"\nOutput files: {result.output_files}")
    print(f"Execution time: {result.execution_time:.2f} seconds")
    print()

    return result.success


async def test_r_venn():
    """Test the R Venn diagram example via MCP tool."""
    print("=" * 60)
    print("Testing R Venn Diagram via MCP Tool")
    print("=" * 60)

    script_path = Path(__file__).parent / "scripts/venn_diagram_script.R"
    script_content = script_path.read_text()

    # Create input model (simulating MCP tool call)
    params = RExecutorInput(
        script=script_content,
        packages=["VennDiagram"],
        input_files={},
        timeout=300,
    )

    result = await coala_r_executor(params)

    print(f"Success: {result.success}")
    print(f"Exit code: {result.exit_code}")
    print(f"\nStdout:\n{result.stdout}")
    if result.stderr:
        print(f"\nStderr:\n{result.stderr[:500]}")
    print(f"\nOutput files: {result.output_files}")
    print(f"Execution time: {result.execution_time:.2f} seconds")
    print()

    return result.success


async def test_pdf_extraction():
    """Test the PDF extraction example via MCP tool."""
    print("=" * 60)
    print("Testing PDF Extraction via MCP Tool")
    print("=" * 60)

    script_path = Path(__file__).parent / "scripts/pdf_extraction_script.py"
    script_content = script_path.read_text()

    # Check if PDF exists
    pdf_path = Path("/tmp/background-checks.pdf")
    if not pdf_path.exists():
        print("PDF file not found. Downloading...")
        import subprocess

        subprocess.run(
            [
                "curl",
                "-s",
                "https://raw.githubusercontent.com/jsvine/pdfplumber/stable/examples/pdfs/background-checks.pdf",
                "-o",
                str(pdf_path),
            ],
            check=True,
        )

    # Create input model (simulating MCP tool call)
    params = PythonExecutorInput(
        script=script_content,
        packages=["pdfplumber"],
        input_files={"/input/background-checks.pdf": str(pdf_path)},
        timeout=300,
    )

    result = await coala_python_executor(params)

    print(f"Success: {result.success}")
    print(f"Exit code: {result.exit_code}")
    print(f"\nStdout:\n{result.stdout[:1000]}")
    if result.stderr:
        print(f"\nStderr:\n{result.stderr[:500]}")
    print(f"\nOutput files: {result.output_files}")
    print(f"Execution time: {result.execution_time:.2f} seconds")
    print()

    return result.success


async def main():
    """Run all tests via MCP tools."""
    print("Testing Coala Runtime MCP Server Tools")
    print("=" * 60)
    print()

    results = []

    # Test Python boxplot
    try:
        success = await test_python_boxplot()
        results.append(("Python Boxplot (MCP)", success))
    except Exception as e:
        print(f"Error testing Python boxplot: {e}")
        import traceback

        traceback.print_exc()
        results.append(("Python Boxplot (MCP)", False))

    # Test R Venn diagram
    try:
        success = await test_r_venn()
        results.append(("R Venn Diagram (MCP)", success))
    except Exception as e:
        print(f"Error testing R Venn diagram: {e}")
        import traceback

        traceback.print_exc()
        results.append(("R Venn Diagram (MCP)", False))

    # Test PDF extraction
    try:
        success = await test_pdf_extraction()
        results.append(("PDF Extraction (MCP)", success))
    except Exception as e:
        print(f"Error testing PDF extraction: {e}")
        import traceback

        traceback.print_exc()
        results.append(("PDF Extraction (MCP)", False))

    # Summary
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)
    for test_name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status}: {test_name}")

    all_passed = all(success for _, success in results)
    print()
    if all_passed:
        print("All MCP tool tests passed!")
        return 0
    else:
        print("Some MCP tool tests failed.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
