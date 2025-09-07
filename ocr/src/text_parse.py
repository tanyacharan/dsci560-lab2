import os
import json
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import hashlib

import openai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class NewsletterProcessor:
    """Process newsletter documents through OpenAI API"""
    
    def __init__(self, model: str = "gpt-3.5-turbo-1106"):
        """
        Initialize with OpenAI client and configuration
        
        Args:
            model: OpenAI model to use
        """
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model
        
    
    def _create_prompt(self, text: str, date_info: str = None) -> str:
        """Create the extraction prompt for the newsletter"""
        date_instruction = f"Use this date: {date_info}. " if date_info else "Find the date in the newsletter text. "
        
        return f"""Extract ALL key information from this newsletter into a single dense paragraph.

        IMPORTANT: {date_instruction}Start with "On [DATE], Morning Brew reported..." using the actual date.

        Include:
        - The date (from filename or newsletter text)
        - Market movements with exact numbers and percentages  
        - All major stories with specific numbers, dollar amounts, and percentages
        - Company actions, regulatory decisions, and political developments
        - Key implications and context

        Newsletter text: {text}

        Write summary starting with the real date:"""

    def process_document(self, text: str, doc_id: str = None, filename: str = None) -> Optional[str]:
        """
        Process a single document through OpenAI API
        
        Args:
            text: The document text to process
            doc_id: Optional identifier for logging
            filename: Optional filename to extract date from
            
        Returns:
            Processed summary or None if failed
        """        
        # Extract date from filename if available
        date_info = None
        if filename:
            import re
            # Look for date patterns like "Sep 7 2025" at end of filename
            date_match = re.search(r'([A-Za-z]{3}\s+\d{1,2}\s+\d{4})', filename)
            if date_match:
                date_info = date_match.group(1)
                logger.info(f"Extracted date from filename: {date_info}")
            else:
                logger.warning(f"No date found in filename: {filename}")
        
        # Process through API with retries
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info(f"Processing document {doc_id} (attempt {attempt + 1})")
                
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system", 
                            "content": "You are a data extraction specialist. Create dense, comprehensive summaries that preserve all important facts, numbers, and context from newsletters."
                        },
                        {
                            "role": "user",
                            "content": self._create_prompt(text, date_info)
                        }
                    ],
                    temperature=0.3,  # Lower temperature for consistency
                    max_tokens=1200   # Generous output allowance for dense paragraphs
                )
                
                result = response.choices[0].message.content
                
                # Post-process: Format dates properly
                if result and date_info:
                    try:
                        import re
                        from datetime import datetime
                        date_obj = datetime.strptime(date_info, "%b %d %Y")
                        
                        # Format with ordinal suffix (1st, 2nd, 3rd, 4th, etc.)
                        day = date_obj.day
                        if 4 <= day <= 20 or 24 <= day <= 30:
                            suffix = "th"
                        else:
                            suffix = ["st", "nd", "rd"][day % 10 - 1]
                        formatted_date = f"{date_obj.strftime('%B')} {day}{suffix}, {date_obj.year}"
                        
                        # Replace both [date] and raw date formats
                        if "[date]" in result:
                            result = result.replace("[date]", formatted_date)
                            logger.info(f"Replaced [date] with {formatted_date}")
                        elif date_info in result:
                            result = result.replace(date_info, formatted_date)
                            logger.info(f"Replaced raw date {date_info} with {formatted_date}")
                        
                    except Exception as e:
                        logger.warning(f"Date formatting failed: {e}")
                        # Fallback: just replace [date] if it exists
                        if "[date]" in result and date_info:
                            result = result.replace("[date]", date_info)
                            logger.info(f"FALLBACK: Replaced [date] with raw date {date_info}")
                
                return result
                
            except openai.RateLimitError as e:
                wait_time = min(60 * (2 ** attempt), 300)  # Exponential backoff, max 5 min
                logger.warning(f"Rate limit hit: {e}. Waiting {wait_time}s...")
                time.sleep(wait_time)
                
            except Exception as e:
                logger.error(f"Error processing document {doc_id}: {e}")
                if attempt == max_retries - 1:
                    logger.error(f"Failed to process document {doc_id} after {max_retries} attempts")
                    return None
                time.sleep(5)
        
        return None
    
    def process_batch(self, documents: List[Dict]) -> List[Dict]:
        """
        Process multiple documents with progress tracking
        """
        results = []
        total = len(documents)
        
        # Use the output directory that was set by the pipeline
        output_dir = getattr(self, 'output_dir', None)
        if output_dir is None:
            # Fallback for standalone usage
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_dir = Path(f"processed_{timestamp}")
            output_dir.mkdir(exist_ok=True)
        else:
            output_dir = Path(output_dir)
            output_dir.mkdir(exist_ok=True)
        
        # Create subdirectory for individual files
        individual_dir = output_dir / "individual_summaries"
        individual_dir.mkdir(exist_ok=True)
        
        logger.info(f"Starting processing of {total} documents")
        logger.info(f"Output directory: {output_dir}")
        
        for i, doc in enumerate(documents, 1):
            doc_id = doc.get('id', f'doc_{i}')
            logger.info(f"Processing {i}/{total}: {doc_id}")
            
            # Process the document
            summary = self.process_document(doc['text'], doc_id, doc.get('filename'))
            
            if summary:
                # Extract date from summary for sorting (assumes "On [date]," format)
                import re
                date_match = re.search(r'On ([^,]+), \d{4}', summary)
                doc_date = date_match.group(0) if date_match else None
                
                result = {
                    'id': doc_id,
                    'filename': doc.get('filename', 'unknown'),
                    'summary': summary,
                    'date_string': doc_date,
                    'processed_at': datetime.now().isoformat(),
                    'word_count': len(summary.split())
                }
                results.append(result)
                
                # Save individual file
                individual_file = individual_dir / f"{doc_id}.txt"
                with open(individual_file, 'w', encoding='utf-8') as f:
                    f.write(summary)
                
                # Also save to JSONL for metadata
                jsonl_file = output_dir / "processed_metadata.jsonl"
                with open(jsonl_file, 'a') as f:
                    f.write(json.dumps(result) + '\n')
                
                logger.info(f"Successfully processed {doc_id} ({len(summary.split())} words)")
            else:
                logger.error(f"Failed to process {doc_id}")
            
            if i < total:
                time.sleep(1)
        
        # Sort results by date (reverse chronological)
        results = sorted(results, key=lambda x: x.get('date_string') or '', reverse=True)
        
        # Create combined file in reverse chronological order
        combined_file = output_dir / "training_data_combined.txt"
        with open(combined_file, 'w', encoding='utf-8') as f:
            for result in results:
                f.write(result['summary'])
                f.write("\n\n")
        
        # Create CSV-ready file
        csv_file = output_dir / "summaries_for_csv.txt"
        with open(csv_file, 'w', encoding='utf-8') as f:
            f.write("document_id|summary\n")  # Header
            for result in results:
                # Escape any pipes in the summary
                clean_summary = result['summary'].replace('|', '\\|')
                f.write(f"{result['id']}|{clean_summary}\n")
        
        logger.info(f"Completed processing. {len(results)}/{total} successful")
        logger.info(f"Individual files saved in: {individual_dir}")
        logger.info(f"Combined file (reverse chronological): {combined_file}")
        logger.info(f"CSV-ready file: {csv_file}")
        
        return results


def load_documents(directory: str) -> List[Dict]:
    """
    Load all text documents from a directory
    
    Args:
        directory: Path to directory containing text files
        
    Returns:
        List of document dictionaries
    """
    documents = []
    path = Path(directory)
    
    if not path.exists():
        logger.error(f"Directory {directory} does not exist")
        return documents
    
    # Support both .txt files and other text formats
    for file_path in path.glob("*.txt"):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if content.strip():  # Only add non-empty files
                    documents.append({
                        'id': file_path.stem,
                        'filename': file_path.name,
                        'text': content
                    })
                    logger.info(f"Loaded {file_path.name}")
        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")
    
    logger.info(f"Loaded {len(documents)} documents")
    return documents

def main():
    """Main execution function"""
    # Configuration
    TEXT_DIR = "extracted_text"  # Change this to your directory
    
    print("\nMorning Brew OCR Text Processing Tool")
    print("-" * 30)
    
    # Load documents
    documents = load_documents(TEXT_DIR)
    
    if not documents:
        print("No documents found to process")
        return
    
    # Confirm before processing
    response = input(f"\nProceed with processing {len(documents)} documents? (y/n): ")
    if response.lower() != 'y':
        print("Processing cancelled")
        return
    
    # Process documents
    processor = NewsletterProcessor()
    results = processor.process_batch(documents)
    
    print("\nProcessing complete!")
    print("Check your output files for the processed summaries.")


if __name__ == "__main__":
    main()