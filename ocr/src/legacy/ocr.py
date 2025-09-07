"""
Simple OCR Script - Tesseract Only
===================================
Just Tesseract OCR, no PyMuPDF dependency issues.

Requirements:
    pip install pytesseract pdf2image pillow tqdm
    
System:
    - Tesseract: download from https://github.com/UB-Mannheim/tesseract/wiki (Windows)
    - Poppler: download from http://blog.alivate.com.au/poppler-windows/ (Windows)
"""

import os
from pathlib import Path
from typing import List, Dict
import argparse

try:
    import pytesseract
    from pdf2image import convert_from_path
    from PIL import Image
    from tqdm import tqdm
except ImportError as e:
    print(f"Missing required package: {e}")
    print("\nInstall with:")
    print("pip install pytesseract pdf2image pillow tqdm")
    exit(1)


def ocr_pdf(pdf_path: str, output_dir: str = "extracted_text", dpi: int = 200) -> str:
    """
    OCR a single PDF using Tesseract.
    
    Args:
        pdf_path: Path to PDF file
        output_dir: Directory to save extracted text
        dpi: DPI for conversion (higher = better quality but slower)
        
    Returns:
        Extracted text
    """
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    if not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_path}")
        return ""
    
    print(f"Processing: {pdf_path.name}")
    
    # Output text file
    output_file = output_dir / f"{pdf_path.stem}.txt"
    
    # Check if already processed
    if output_file.exists():
        print(f"  Already processed, reading from {output_file}")
        with open(output_file, 'r', encoding='utf-8') as f:
            return f.read()
    
    try:
        # Convert PDF to images
        print(f"  Converting to images at {dpi} DPI...")
        images = convert_from_path(pdf_path, dpi=dpi)
        
        text_parts = []
        
        # OCR each page
        for page_num, image in enumerate(tqdm(images, desc="  OCR pages", leave=False)):
            # Convert to grayscale for better OCR
            if image.mode != 'L':
                image = image.convert('L')
            
            # Run OCR
            text = pytesseract.image_to_string(image, lang='eng')
            
            if text.strip():
                text_parts.append(f"=== Page {page_num + 1} ===\n{text}")
        
        # Combine all pages
        full_text = "\n\n".join(text_parts)
        
        # Save to file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(full_text)
        
        print(f"  Saved to: {output_file}")
        print(f"  Extracted {len(full_text)} characters from {len(images)} pages")
        
        return full_text
        
    except Exception as e:
        print(f"  Error: {str(e)}")
        return ""


def ocr_all_pdfs(input_dir: str = "pdfs", output_dir: str = "extracted_text", dpi: int = 200) -> Dict[str, str]:
    """
    OCR all PDFs in a directory.
    
    Args:
        input_dir: Directory containing PDFs
        output_dir: Directory to save text files
        dpi: DPI for conversion
        
    Returns:
        Dictionary mapping filenames to extracted text
    """
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    
    # Create output directory
    output_dir.mkdir(exist_ok=True)
    
    # Find all PDFs
    pdf_files = list(input_dir.glob("*.pdf"))
    
    if not pdf_files:
        print(f"No PDF files found in {input_dir}")
        return {}
    
    print(f"Found {len(pdf_files)} PDF files")
    print("=" * 50)
    
    results = {}
    successful = 0
    failed = 0
    
    for pdf_path in pdf_files:
        text = ocr_pdf(pdf_path, output_dir, dpi)
        
        if text:
            results[pdf_path.name] = text
            successful += 1
        else:
            failed += 1
    
    print("=" * 50)
    print(f"Complete! Successfully processed: {successful}, Failed: {failed}")
    print(f"Text files saved to: {output_dir}")
    
    return results


def main():
    """Main function with command line interface."""
    parser = argparse.ArgumentParser(description="OCR PDFs using Tesseract")
    parser.add_argument("--input-dir", default="pdfs", help="Directory containing PDFs (default: pdfs)")
    parser.add_argument("--output-dir", default="extracted_text", help="Output directory (default: extracted_text)")
    parser.add_argument("--dpi", type=int, default=200, help="DPI for PDF to image conversion (default: 200)")
    parser.add_argument("--single", help="Process a single PDF file")
    
    args = parser.parse_args()
    
    # Check if Tesseract is installed
    try:
        tesseract_version = pytesseract.get_tesseract_version()
        print(f"Tesseract version: {tesseract_version}")
    except Exception as e:
        print("Error: Tesseract not found!")
        print("\nWindows: Download from https://github.com/UB-Mannheim/tesseract/wiki")
        print("Mac: brew install tesseract")
        print("Linux: sudo apt-get install tesseract-ocr")
        return
    
    if args.single:
        # Process single PDF
        print(f"Processing single PDF: {args.single}")
        text = ocr_pdf(args.single, args.output_dir, args.dpi)
        if text:
            print(f"Successfully extracted {len(text)} characters")
    else:
        # Process all PDFs
        ocr_all_pdfs(args.input_dir, args.output_dir, args.dpi)


if __name__ == "__main__":
    main()