#!/usr/bin/env python3
"""
Morning Brew Newsletter Pipeline
================================
Integrated pipeline that runs:
1. url_scraper -> Scrapes URLs from Morning Brew archive
2. pdf_generator_v2 -> Converts URLs to PDFs
3. ocr2 -> Extracts text from PDFs
4. text_parse -> Processes text through OpenAI API

Usage:
    python pipeline.py [--steps STEPS] [--limit LIMIT]
    
Examples:
    python pipeline.py                    # Run full pipeline
    python pipeline.py --steps scrape     # Only scrape URLs
    python pipeline.py --steps pdf,ocr    # Generate PDFs and extract text
    python pipeline.py --limit 10         # Process only 10 articles
"""

import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime
import time
import json
from typing import List, Dict, Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from url_scraper import scrape_morning_brew_urls, save_urls
from pdf_generator_v2 import MorningBrewPDFGenerator
from ocr2 import PDFTextExtractor
from text_parse import NewsletterProcessor, load_documents

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MorningBrewPipeline:
    """Orchestrates the full Morning Brew processing pipeline"""
    
    def __init__(self, output_base: str = "results"):
        """
        Initialize the pipeline
        
        Args:
            output_base: Base directory for all output
        """
        self.output_base = Path(output_base)
        self.output_base.mkdir(exist_ok=True)
        
        # Create timestamped run directory
        self.run_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.run_dir = self.output_base / f"run_{self.run_id}"
        self.run_dir.mkdir(exist_ok=True)
        
        # Setup subdirectories
        self.urls_dir = self.run_dir / "urls"
        self.pdfs_dir = self.run_dir / "pdfs"
        self.text_dir = self.run_dir / "extracted_text"
        self.processed_dir = self.run_dir / "processed"
        
        for dir_path in [self.urls_dir, self.pdfs_dir, self.text_dir, self.processed_dir]:
            dir_path.mkdir(exist_ok=True)
        
        # Pipeline state
        self.state = {
            "run_id": self.run_id,
            "status": "initialized",
            "steps_completed": [],
            "urls": [],
            "pdfs": [],
            "texts": [],
            "processed": []
        }
        self._save_state()
    
    def _save_state(self):
        """Save pipeline state for resumability"""
        state_file = self.run_dir / "pipeline_state.json"
        with open(state_file, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def _load_state(self, run_dir: Optional[Path] = None) -> bool:
        """Load existing pipeline state if available"""
        if run_dir:
            state_file = run_dir / "pipeline_state.json"
            if state_file.exists():
                with open(state_file, 'r') as f:
                    self.state = json.load(f)
                    self.run_id = self.state["run_id"]
                    self.run_dir = run_dir
                    return True
        return False
    
    def step_scrape_urls(self, max_clicks: int = 100, headless: bool = False) -> List[Dict]:
        """
        Step 1: Scrape URLs from Morning Brew archive
        """
        logger.info("=" * 60)
        logger.info("STEP 1: SCRAPING URLS")
        logger.info("=" * 60)
        
        # Check if already completed
        if "scrape_urls" in self.state["steps_completed"]:
            logger.info("URLs already scraped, loading from file...")
            urls_file = self.urls_dir / "urls_latest.json"
            with open(urls_file, 'r') as f:
                data = json.load(f)
                self.state["urls"] = data["articles"]
                return data["articles"]
        
        # Scrape new URLs
        articles = scrape_morning_brew_urls(headless=headless, max_clicks=max_clicks)
        
        if articles:
            # Save URLs (this function returns the JSON file path)
            json_file = save_urls(articles, output_dir=str(self.urls_dir))
            logger.info(f"Scraped {len(articles)} URLs")
            
            # Update state
            self.state["urls"] = articles
            self.state["steps_completed"].append("scrape_urls")
            self.state["status"] = "urls_scraped"
            self._save_state()
            
            return articles
        else:
            logger.error("No URLs scraped!")
            return []
    
    def step_generate_pdfs(self, limit: int = 30, start_from: int = 0) -> List[Path]:
        """
        Step 2: Generate PDFs from URLs
        """
        logger.info("=" * 60)
        logger.info("STEP 2: GENERATING PDFS")
        logger.info("=" * 60)
        
        # Check if already completed
        if "generate_pdfs" in self.state["steps_completed"]:
            logger.info("PDFs already generated, skipping...")
            return [self.pdfs_dir / pdf for pdf in self.state["pdfs"]]
        
        # Check prerequisites
        if not self.state["urls"]:
            logger.error("No URLs available. Run step 1 first.")
            return []
        
        # Generate PDFs
        with MorningBrewPDFGenerator(output_dir=str(self.pdfs_dir)) as generator:
            # Create temporary URLs file for the generator
            temp_urls_file = self.urls_dir / "urls_latest.json"
            with open(temp_urls_file, 'w') as f:
                json.dump({
                    'scrape_date': datetime.now().isoformat(),
                    'total': len(self.state["urls"]),
                    'articles': self.state["urls"]
                }, f, indent=2)
            
            pdf_paths = generator.process_urls(
                urls_file=str(temp_urls_file),
                limit=limit,
                start_from=start_from
            )
            
            # Update state
            self.state["pdfs"] = [pdf.name for pdf in pdf_paths]
            self.state["steps_completed"].append("generate_pdfs")
            self.state["status"] = "pdfs_generated"
            self._save_state()
            
            return pdf_paths
    
    def step_extract_text(self, force_ocr: bool = False) -> Dict[str, str]:
        """
        Step 3: Extract text from PDFs
        """
        logger.info("=" * 60)
        logger.info("STEP 3: EXTRACTING TEXT")
        logger.info("=" * 60)
        
        # Check if already completed
        if "extract_text" in self.state["steps_completed"]:
            logger.info("Text already extracted, loading from files...")
            results = {}
            for txt_file in self.text_dir.glob("*.txt"):
                with open(txt_file, 'r', encoding='utf-8') as f:
                    results[txt_file.stem] = f.read()
            return results
        
        # Check prerequisites
        if not self.state["pdfs"]:
            logger.error("No PDFs available. Run step 2 first.")
            return {}
        
        # Extract text
        extractor = PDFTextExtractor(output_dir=str(self.text_dir))
        results = extractor.process_directory(
            input_dir=str(self.pdfs_dir),
            force_ocr=force_ocr
        )
        
        # Update state
        self.state["texts"] = list(results.keys())
        self.state["steps_completed"].append("extract_text")
        self.state["status"] = "text_extracted"
        self._save_state()
        
        return results
    
    def step_process_text(self) -> List[Dict]:
        """
        Step 4: Process text through OpenAI API
        """
        logger.info("=" * 60)
        logger.info("STEP 4: PROCESSING TEXT WITH AI")
        logger.info("=" * 60)
        
        # Check if already completed
        if "process_text" in self.state["steps_completed"]:
            logger.info("Text already processed")
            return self.state["processed"]
        
        # Check prerequisites
        if not self.state["texts"]:
            logger.error("No text files available. Run step 3 first.")
            return []
        
        # Check for API key
        import os
        if not os.getenv("OPENAI_API_KEY"):
            logger.error("OPENAI_API_KEY not set in environment variables!")
            logger.error("Please set it with: export OPENAI_API_KEY='your-key-here'")
            return []
        
        # Load documents
        documents = load_documents(str(self.text_dir))
        
        if not documents:
            logger.error("No documents loaded from text directory")
            return []
        
        # Process through AI
        processor = NewsletterProcessor()
        
        # Update output directory to our processed directory
        processor.output_dir = self.processed_dir
        
        results = processor.process_batch(documents)
        
        # Update state
        self.state["processed"] = results
        self.state["steps_completed"].append("process_text")
        self.state["status"] = "completed"
        self._save_state()
        
        return results
    
    def run_pipeline(self, steps: Optional[List[str]] = None, 
                    limit: int = 30, 
                    max_clicks: Optional[int] = None,
                    headless: bool = True,
                    force_ocr: bool = False) -> Dict:
        """
        Run the full pipeline or specific steps
        
        Args:
            steps: List of steps to run. If None, runs all steps.
                   Options: ["scrape", "pdf", "ocr", "parse"]
            limit: Maximum number of articles to process
            max_clicks: Maximum number of "Load More" clicks (default: calculated from limit)
            headless: Run browser in headless mode
            force_ocr: Force OCR even if text can be extracted directly
            
        Returns:
            Dictionary with pipeline results
        """
        all_steps = ["scrape", "pdf", "ocr", "parse"]
        steps_to_run = steps or all_steps
        
        # Calculate max_clicks based on limit if not provided (each "Load More" loads ~10 articles)
        if max_clicks is None:
            max_clicks = max(1, int(limit / 10))
        
        logger.info(f"Starting pipeline run: {self.run_id}")
        logger.info(f"Steps to run: {steps_to_run}")
        logger.info(f"Article limit: {limit}, Max clicks: {max_clicks}")
        logger.info(f"Output directory: {self.run_dir}")
        
        results = {
            "run_id": self.run_id,
            "run_dir": str(self.run_dir),
            "steps_run": steps_to_run,
            "results": {}
        }
        
        # Step 1: Scrape URLs
        if "scrape" in steps_to_run:
            urls = self.step_scrape_urls(max_clicks=max_clicks, headless=headless)
            results["results"]["urls"] = len(urls)
            
            if not urls:
                logger.error("No URLs scraped, stopping pipeline")
                return results
        
        # Step 2: Generate PDFs
        if "pdf" in steps_to_run:
            pdfs = self.step_generate_pdfs(limit=limit)
            results["results"]["pdfs"] = len(pdfs)
            
            if not pdfs:
                logger.error("No PDFs generated, stopping pipeline")
                return results
        
        # Step 3: Extract text (OCR)
        if "ocr" in steps_to_run:
            texts = self.step_extract_text(force_ocr=force_ocr)
            results["results"]["texts"] = len(texts)
            
            if not texts:
                logger.error("No text extracted, stopping pipeline")
                return results
        
        # Step 4: Parse/process text
        if "parse" in steps_to_run:
            processed = self.step_process_text()
            results["results"]["processed"] = len(processed)
        
        # Final summary
        logger.info("=" * 60)
        logger.info("PIPELINE COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Run ID: {self.run_id}")
        logger.info(f"Output directory: {self.run_dir}")
        
        for step, count in results["results"].items():
            logger.info(f"{step}: {count} items")
        
        # Save final results
        results_file = self.run_dir / "pipeline_results.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        return results


def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(
        description="Morning Brew Newsletter Processing Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python pipeline.py                         # Run full pipeline (30 articles, 3 clicks)
    python pipeline.py --steps scrape pdf      # Only scrape and generate PDFs  
    python pipeline.py --limit 50              # Process 50 articles (auto: 5 clicks)
    python pipeline.py --limit 10 --max-clicks 2  # Override click calculation
    python pipeline.py --headless             # Run browser in headless mode
    python pipeline.py --resume run_20241206   # Resume from previous run
        """
    )
    
    parser.add_argument(
        "--steps", 
        nargs="+",
        choices=["scrape", "pdf", "ocr", "parse"],
        help="Steps to run (default: all)"
    )
    
    parser.add_argument(
        "--limit",
        type=int,
        default=30,
        help="Maximum number of articles to process (default: 30)"
    )
    
    parser.add_argument(
        "--max-clicks",
        type=int,
        help="Maximum number of 'Load More' clicks for scraping (default: calculated from limit)"
    )
    
    parser.add_argument(
        "--no-headless",
        action="store_true", 
        help="Show browser window (default is headless)"
    )
    
    parser.add_argument(
        "--force-ocr",
        action="store_true",
        help="Force OCR even if text can be extracted directly"
    )
    
    parser.add_argument(
        "--output-dir",
        default="results",
        help="Base output directory (default: results)"
    )
    
    parser.add_argument(
        "--resume",
        help="Resume from a previous run directory"
    )
    
    args = parser.parse_args()
    
    # Print banner
    print("""
╔══════════════════════════════════════════════════════════════════╗
║           Morning Brew Newsletter Processing Pipeline            ║
║                                                                  ║
║  1. Scrape URLs → 2. Generate PDFs → 3. Extract Text → 4. AI    ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    
    # Create or resume pipeline
    if args.resume:
        resume_dir = Path(args.output_dir) / args.resume
        if not resume_dir.exists():
            print(f"Error: Resume directory not found: {resume_dir}")
            sys.exit(1)
        
        pipeline = MorningBrewPipeline(output_base=args.output_dir)
        if not pipeline._load_state(resume_dir):
            print(f"Error: No pipeline state found in {resume_dir}")
            sys.exit(1)
        
        print(f"Resuming pipeline from: {resume_dir}")
    else:
        pipeline = MorningBrewPipeline(output_base=args.output_dir)
    
    try:
        # Run pipeline
        results = pipeline.run_pipeline(
            steps=args.steps,
            limit=args.limit,
            max_clicks=args.max_clicks,
            headless=not args.no_headless,  # Invert: headless by default unless --no-headless
            force_ocr=args.force_ocr
        )
        
        print("\n✓ Pipeline completed successfully!")
        print(f"Results saved in: {results['run_dir']}")
        
    except KeyboardInterrupt:
        print("\n\n⚠ Pipeline interrupted by user")
        print(f"To resume, run: python pipeline.py --resume run_{pipeline.run_id}")
    except Exception as e:
        print(f"\n✗ Pipeline failed with error: {e}")
        logger.exception("Pipeline error")
        sys.exit(1)


if __name__ == "__main__":
    main()