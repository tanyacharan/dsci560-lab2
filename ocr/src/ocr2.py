"""
Clean PDF OCR Script
====================
Extracts text from PDFs using PyMuPDF and Tesseract OCR.

Setup:
    pip uninstall fitz  # Remove conflicting package if present
    pip install --upgrade PyMuPDF pytesseract pillow tqdm
    
    Windows: Install Tesseract from:
    https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-setup-5.3.3.20231005.exe
"""

import os
import sys
import io
from pathlib import Path
from typing import Optional, Dict, List

# Check for correct PyMuPDF installation
try:
    import fitz
    if hasattr(fitz, '__version__'):
        print(f"✓ PyMuPDF version: {fitz.__version__}")
    else:
        print("⚠ Wrong fitz package detected!")
        print("Fix with:")
        print("  pip uninstall fitz")
        print("  pip install --upgrade PyMuPDF")
        sys.exit(1)
except ImportError:
    print("✗ PyMuPDF not installed")
    print("Install with: pip install PyMuPDF")
    sys.exit(1)

# Import other requirements
try:
    import pytesseract
    from PIL import Image
    from tqdm import tqdm
except ImportError as e:
    print(f"✗ Missing package: {e}")
    print("Install with: pip install pytesseract pillow tqdm")
    sys.exit(1)


class PDFTextExtractor:
    """
    Extract text from PDFs using PyMuPDF and OCR fallback.
    """
    
    def __init__(self, output_dir: str = "extracted_text"):
        """
        Initialize the extractor.
        
        Args:
            output_dir: Directory to save extracted text files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Setup Tesseract for Windows
        self._setup_tesseract()
        
        # Statistics
        self.stats = {
            "processed": 0,
            "direct_text": 0,
            "ocr_used": 0,
            "failed": 0
        }
    
    def _setup_tesseract(self):
        """Configure Tesseract path for Windows."""
        if sys.platform != "win32":
            return  # Not Windows, assume tesseract is in PATH
        
        # Common Windows Tesseract locations
        tesseract_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            r"C:\Tesseract-OCR\tesseract.exe",
        ]
        
        for tess_path in tesseract_paths:
            if Path(tess_path).exists():
                pytesseract.pytesseract.tesseract_cmd = tess_path
                print(f"✓ Tesseract found: {tess_path}")
                return
        
        # Try to run tesseract from PATH
        try:
            import subprocess
            result = subprocess.run(["tesseract", "--version"], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print("✓ Tesseract found in PATH")
                return
        except:
            pass
        
        print("⚠ Tesseract not found. OCR may not work.")
        print("  Download from: https://github.com/UB-Mannheim/tesseract/wiki")
    
    def extract_pdf(self, pdf_path: str, force_ocr: bool = False) -> Optional[str]:
        """
        Extract text from a single PDF.
        
        Args:
            pdf_path: Path to PDF file
            force_ocr: If True, skip text extraction and use OCR directly
            
        Returns:
            Extracted text or None if failed
        """
        pdf_path = Path(pdf_path)
        
        # Check if file exists
        if not pdf_path.exists():
            print(f"✗ File not found: {pdf_path}")
            return None
        
        print(f"\nProcessing: {pdf_path.name}")
        
        try:
            # Open PDF
            pdf_doc = fitz.open(str(pdf_path))
            total_pages = len(pdf_doc)
            print(f"  Pages: {total_pages}")
            
            # Try direct text extraction first (unless forced to OCR)
            if not force_ocr:
                text = self._extract_text_direct(pdf_doc)
                if text and len(text.strip()) > 100:  # Minimum threshold
                    print(f"  ✓ Extracted text directly ({len(text)} chars)")
                    pdf_doc.close()
                    self.stats["direct_text"] += 1
                    return text
            
            # Fall back to OCR
            print("  Using OCR (this may take a moment)...")
            text = self._extract_text_ocr(pdf_doc)
            pdf_doc.close()
            
            if text:
                print(f"  ✓ OCR complete ({len(text)} chars)")
                self.stats["ocr_used"] += 1
                return text
            else:
                print("  ✗ No text extracted")
                self.stats["failed"] += 1
                return None
                
        except Exception as e:
            print(f"  ✗ Error: {str(e)}")
            self.stats["failed"] += 1
            return None
    
    def _extract_text_direct(self, pdf_doc) -> str:
        """
        Extract embedded text from PDF (fast method).
        
        Args:
            pdf_doc: PyMuPDF document object
            
        Returns:
            Extracted text
        """
        text_parts = []
        
        for page_num in range(len(pdf_doc)):
            page = pdf_doc[page_num]
            text = page.get_text()
            
            if text.strip():
                text_parts.append(f"--- Page {page_num + 1} ---\n{text}")
        
        return "\n\n".join(text_parts)
    
    def _extract_text_ocr(self, pdf_doc) -> str:
        """
        Extract text using OCR (slow but thorough).
        
        Args:
            pdf_doc: PyMuPDF document object
            
        Returns:
            Extracted text
        """
        text_parts = []
        
        # Process each page
        for page_num in tqdm(range(len(pdf_doc)), desc="  OCR progress"):
            page = pdf_doc[page_num]
            
            # Convert page to high-quality image
            matrix = fitz.Matrix(2.0, 2.0)  # 2x zoom for better OCR
            pix = page.get_pixmap(matrix=matrix)
            
            # Convert to PIL Image
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            
            # Convert to grayscale for better OCR
            if img.mode != 'L':
                img = img.convert('L')
            
            # Run OCR
            try:
                text = pytesseract.image_to_string(img, lang='eng')
                
                if text.strip():
                    text_parts.append(f"--- Page {page_num + 1} ---\n{text}")
            except Exception as e:
                print(f"    OCR error on page {page_num + 1}: {str(e)}")
        
        return "\n\n".join(text_parts)
    
    def process_directory(self, input_dir: str = "pdfs", 
                         force_ocr: bool = False) -> Dict[str, str]:
        """
        Process all PDFs in a directory.
        
        Args:
            input_dir: Directory containing PDFs
            force_ocr: If True, use OCR for all files
            
        Returns:
            Dictionary mapping filenames to extracted text
        """
        input_dir = Path(input_dir)
        
        # Find all PDFs
        pdf_files = list(input_dir.glob("*.pdf"))
        
        if not pdf_files:
            print(f"No PDF files found in: {input_dir}")
            return {}
        
        print(f"Found {len(pdf_files)} PDF files")
        print("=" * 60)
        
        results = {}
        
        for pdf_path in pdf_files:
            # Check if already processed
            output_file = self.output_dir / f"{pdf_path.stem}.txt"
            
            if output_file.exists() and not force_ocr:
                print(f"\n✓ Already processed: {pdf_path.name}")
                with open(output_file, 'r', encoding='utf-8') as f:
                    results[pdf_path.name] = f.read()
                continue
            
            # Extract text
            self.stats["processed"] += 1
            text = self.extract_pdf(pdf_path, force_ocr=force_ocr)
            
            if text:
                # Save to file
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(text)
                results[pdf_path.name] = text
                print(f"  → Saved to: {output_file}")
        
        # Print statistics
        self._print_stats()
        
        return results
    
    def _print_stats(self):
        """Print extraction statistics."""
        print("\n" + "=" * 60)
        print("EXTRACTION COMPLETE")
        print("=" * 60)
        print(f"Total processed: {self.stats['processed']}")
        print(f"Direct text extraction: {self.stats['direct_text']}")
        print(f"OCR used: {self.stats['ocr_used']}")
        print(f"Failed: {self.stats['failed']}")
        
        if self.stats['processed'] > 0:
            success_rate = ((self.stats['direct_text'] + self.stats['ocr_used']) / 
                          self.stats['processed'] * 100)
            print(f"Success rate: {success_rate:.1f}%")
        
        print(f"\nOutput directory: {self.output_dir}")


def main():
    """Main command-line interface."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Extract text from PDFs using PyMuPDF and OCR"
    )
    parser.add_argument(
        "pdf", nargs="?", 
        help="Single PDF file to process (optional)"
    )
    parser.add_argument(
        "--input-dir", default="pdfs",
        help="Input directory for batch processing (default: pdfs)"
    )
    parser.add_argument(
        "--output-dir", default="extracted_text",
        help="Output directory for text files (default: extracted_text)"
    )
    parser.add_argument(
        "--force-ocr", action="store_true",
        help="Force OCR even if text can be extracted directly"
    )
    
    args = parser.parse_args()
    
    # Initialize extractor
    extractor = PDFTextExtractor(output_dir=args.output_dir)
    
    if args.pdf:
        # Process single PDF
        text = extractor.extract_pdf(args.pdf, force_ocr=args.force_ocr)
        
        if text:
            output_file = extractor.output_dir / f"{Path(args.pdf).stem}.txt"
            print(f"\n✓ Text saved to: {output_file}")
        else:
            print("\n✗ Failed to extract text")
    else:
        # Process directory
        print(f"Processing directory: {args.input_dir}")
        results = extractor.process_directory(
            input_dir=args.input_dir,
            force_ocr=args.force_ocr
        )
        
        if results:
            print(f"\n✓ Successfully processed {len(results)} files")
        else:
            print("\n✗ No files were processed")


if __name__ == "__main__":
    main()