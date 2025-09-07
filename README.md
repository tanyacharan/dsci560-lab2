# Morning Brew Newsletter Processing Pipeline

A complete pipeline for scraping, converting, extracting, and processing Morning Brew newsletters into structured training data.

## Overview

This pipeline automates the entire process of:
1. **Scraping URLs** from Morning Brew's archive
2. **Converting articles to PDFs** with clean formatting
3. **Extracting text** using OCR and direct text extraction
4. **Processing with AI** to create dense, comprehensive summaries

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Download ChromeDriver:**
   - Download from [Chrome for Testing](https://googlechromelabs.github.io/chrome-for-testing/)
   - Place `chromedriver.exe` in the `src/` folder

3. **Set up OpenAI API:**
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   ```
   Or create a `.env` file:
   ```
   OPENAI_API_KEY=your-api-key-here
   ```

4. **Run the full pipeline:**
   ```bash
   python pipeline.py
   ```

## Usage Examples

### Full Pipeline
```bash
# Process 30 articles (default)
python pipeline.py

# Process 50 articles
python pipeline.py --limit 50

# Show browser window (default is headless)
python pipeline.py --no-headless
```

### Individual Steps
```bash
# Only scrape URLs
python pipeline.py --steps scrape

# Generate PDFs and extract text
python pipeline.py --steps pdf ocr

# Just process existing text with AI
python pipeline.py --steps parse
```

### Resume Previous Run
```bash
# Resume from a previous run
python pipeline.py --resume run_20250107_144436
```

## Pipeline Steps

### 1. URL Scraper (`url_scraper.py`)
- Scrapes Morning Brew archive using Selenium
- Automatically clicks "Load More" to get more articles
- Filters out generic/promotional links
- Saves URLs with metadata to JSON

**Output:** `results/run_XXXXXX/urls/urls_latest.json`

### 2. PDF Generator (`pdf_generator_v2.py`)
- Converts article URLs to clean PDFs
- Removes headers, footers, ads, and navigation
- Uses Chrome's print-to-PDF for consistent formatting
- Handles JavaScript-heavy pages

**Output:** `results/run_XXXXXX/pdfs/*.pdf`

### 3. Text Extractor (`ocr2.py`)
- Extracts text from PDFs using PyMuPDF
- Falls back to Tesseract OCR for image-based content
- Handles both searchable and scanned PDFs
- Preserves page structure

**Output:** `results/run_XXXXXX/extracted_text/*.txt`

### 4. AI Processor (`text_parse.py`)
- Processes extracted text through OpenAI API
- Creates dense, comprehensive summaries
- Extracts dates from filenames
- Formats output consistently

**Output:** `results/run_XXXXXX/processed/`

## Configuration

### Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--steps` | Steps to run: `scrape`, `pdf`, `ocr`, `parse` | All steps |
| `--limit` | Maximum articles to process | 30 |
| `--max-clicks` | Max "Load More" clicks (auto-calculated) | limit/10 |
| `--no-headless` | Show browser window | Headless |
| `--force-ocr` | Force OCR even if text extractable | False |
| `--resume` | Resume from previous run | None |

### Environment Variables

- `OPENAI_API_KEY`: Required for AI processing step

## Output Structure

```
results/
└── run_20250107_144436/
    ├── urls/
    │   └── urls_latest.json
    ├── pdfs/
    │   ├── 001_Article_Title_Sep_7_2025.pdf
    │   └── 002_Another_Article_Sep_6_2025.pdf
    ├── extracted_text/
    │   ├── 001_Article_Title_Sep_7_2025.txt
    │   └── 002_Another_Article_Sep_6_2025.txt
    ├── processed/
    │   ├── individual_summaries/
    │   ├── training_data_combined.txt
    │   └── summaries_for_csv.txt
    ├── pipeline_state.json
    └── pipeline_results.json
```

## Requirements

### System Dependencies
- **Python 3.8+**
- **Chrome Browser**
- **Tesseract OCR** (for image-based PDFs)
  - Windows: Download from [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki)
  - macOS: `brew install tesseract`
  - Linux: `sudo apt install tesseract-ocr`

### Python Dependencies
See `requirements.txt` for full list. Key packages:
- `selenium` - Web scraping
- `PyMuPDF` - PDF processing  
- `pytesseract` - OCR
- `openai` - AI processing
- `beautifulsoup4` - HTML parsing

## Troubleshooting

### Common Issues

**ChromeDriver not found:**
```
Please download chromedriver.exe and put it in this folder
```
→ Download ChromeDriver and place in `src/` folder

**Tesseract not found:**
```
⚠ Tesseract not found. OCR may not work.
```
→ Install Tesseract OCR system package

**OpenAI API key missing:**
```
OPENAI_API_KEY not found in environment variables
```
→ Set environment variable or create `.env` file

**Rate limiting:**
```
Rate limit hit: ... Waiting 60s...
```
→ Pipeline automatically handles rate limiting with exponential backoff

### Performance Tips

- **Use headless mode** for faster processing (default)
- **Adjust limit** based on your needs (each "Load More" ≈ 10 articles)
- **Resume failed runs** instead of starting over
- **Check logs** for detailed progress information

## Development

### Project Structure
```
ocr/
├── src/                    # Source modules
│   ├── url_scraper.py     # Step 1: URL scraping
│   ├── pdf_generator_v2.py # Step 2: PDF generation  
│   ├── ocr2.py            # Step 3: Text extraction
│   └── text_parse.py      # Step 4: AI processing
├── pipeline.py            # Main orchestrator
├── requirements.txt       # Dependencies
└── README.md             # This file
```

### Adding New Features

The pipeline is modular - each step can be run independently or customized:

1. **Modify individual modules** in `src/` for specific changes
2. **Update pipeline.py** for orchestration changes  
3. **Test individual steps** before running full pipeline
4. **Use resume functionality** for development iterations

## License

This project is for educational and research purposes. Please respect Morning Brew's terms of service and rate limits.
