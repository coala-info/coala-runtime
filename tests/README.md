# Test Scripts

This directory contains test scripts that can be executed using the Coala Runtime MCP server.

## Test Scripts

### Python Tests

#### `test_boxplot.py`
Creates a boxplot visualization using matplotlib with sample data.

**Usage:**
- Packages: None (uses default: numpy, pandas, matplotlib)
- Output: `boxplot_demo.png` in `/output/` directory

#### `test_pdf_extraction.py`
Extracts content from a PDF file using pdfplumber.

**Usage:**
- Packages: `pdfplumber`
- Input files: Requires `/input/background-checks.pdf` to be mounted
- Output: Text and metadata extracted from PDF

**Setup:**
```bash
curl "https://raw.githubusercontent.com/jsvine/pdfplumber/stable/examples/pdfs/background-checks.pdf" > /tmp/background-checks.pdf
```

### R Tests

#### `test_venn_diagram.R`
Creates a Venn diagram visualization using the VennDiagram package.

**Usage:**
- Packages: `VennDiagram`
- Output: `venn_diagram.png` in `/output/` directory

## Running Tests

These scripts can be executed via the MCP server tools:
- `coala_python_executor` for Python scripts
- `coala_r_executor` for R scripts

Example usage through MCP:
- Read the script file content
- Pass it to the appropriate executor tool
- Check the `output_files` array for generated file paths
