"""
Test script for extracting content from a PDF using pdfplumber.
This script demonstrates PDF text and character extraction.
"""

import pdfplumber

# Open the PDF file
with pdfplumber.open("/input/background-checks.pdf") as pdf:
    # Get the first page
    first_page = pdf.pages[0]

    # Print the first character
    if first_page.chars:
        print("First character:", first_page.chars[0])
        print("\nFirst 10 characters:")
        for i, char in enumerate(first_page.chars[:10]):
            print(f"  {i}: {char}")

    # Also extract and print text from the first page
    print("\n" + "=" * 50)
    print("Text from first page:")
    print("=" * 50)
    text = first_page.extract_text()
    if text:
        print(text[:500])  # Print first 500 characters
    else:
        print("No text extracted")

    # Print some metadata
    print("\n" + "=" * 50)
    print("PDF Metadata:")
    print("=" * 50)
    print(f"Number of pages: {len(pdf.pages)}")
    if pdf.metadata:
        print(f"Title: {pdf.metadata.get('Title', 'N/A')}")
        print(f"Author: {pdf.metadata.get('Author', 'N/A')}")
