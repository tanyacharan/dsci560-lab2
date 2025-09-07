"""
Morning Brew PDF Generator
===========================
Step 2: Convert URLs to clean PDFs without headers/footers
"""

import json
import time
from datetime import datetime
from pathlib import Path
import base64

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class MorningBrewPDFGenerator:
    """Generate clean PDFs from Morning Brew articles."""
    
    def __init__(self, output_dir="pdfs"):
        """
        Initialize PDF generator.
        
        Args:
            output_dir: Directory to save PDFs
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Chrome options for PDF generation
        self.chrome_options = Options()
        self.chrome_options.add_argument("--headless=new")  # Must be headless for PDF
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        self.chrome_options.add_argument("--window-size=1920,1080")
        
        # Enable automation for better PDF generation
        self.chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
        self.chrome_options.add_experimental_option('useAutomationExtension', False)
        
        self.driver = None
        
    def __enter__(self):
        """Context manager entry."""
        # Setup driver with local chromedriver
        service = Service(executable_path="./chromedriver.exe")
        self.driver = webdriver.Chrome(service=service, options=self.chrome_options)
        # Enable CDP for PDF generation
        self.driver.execute_cdp_cmd("Page.setDownloadBehavior", {
            "behavior": "allow",
            "downloadPath": str(self.output_dir)
        })
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self.driver:
            self.driver.quit()
    
    def inject_cleanup_css(self):
        """Inject CSS to hide headers, footers, and other unwanted elements."""
        cleanup_css = """
        // Hide Morning Brew header/footer elements
        var style = document.createElement('style');
        style.innerHTML = `
            /* Hide navigation and headers */
            header, nav, .header, .navigation, .nav-bar, 
            [class*="header"], [class*="Header"], 
            [class*="navbar"], [class*="NavBar"] {
                display: none !important;
            }
            
            /* Hide footers */
            footer, .footer, [class*="footer"], [class*="Footer"] {
                display: none !important;
            }
            
            /* Hide subscription prompts and popups */
            [class*="subscribe"], [class*="Subscribe"],
            [class*="newsletter"], [class*="Newsletter"],
            [class*="popup"], [class*="Popup"],
            [class*="modal"], [class*="Modal"],
            [class*="overlay"], [class*="Overlay"],
            [class*="email-preferences"], [class*="unsubscribe"] {
                display: none !important;
            }
            
            /* Hide social sharing buttons */
            [class*="share"], [class*="Share"],
            [class*="social"], [class*="Social"] {
                display: none !important;
            }
            
            /* Hide ads and promotional content */
            [class*="ad-"], [class*="Ad-"],
            [class*="promo"], [class*="Promo"],
            [class*="sponsor"], [class*="Sponsor"] {
                display: none !important;
            }
            
            /* Hide "Back to top" buttons */
            [class*="back-to-top"], [class*="BackToTop"],
            [class*="scroll-to-top"] {
                display: none !important;
            }
            
            /* Clean up spacing */
            body {
                padding-top: 0 !important;
                margin-top: 0 !important;
            }
            
            /* For print/PDF specifically */
            @media print {
                /* Remove all backgrounds to save ink */
                * {
                    background: white !important;
                    color: black !important;
                }
                
                /* Hide elements that shouldn't be in PDF */
                video, audio, iframe, embed, object {
                    display: none !important;
                }
                
                /* Ensure content fits properly */
                body {
                    width: 100% !important;
                    margin: 0 !important;
                    padding: 20px !important;
                }
                
                /* Remove page margins added by browser */
                @page {
                    margin: 0;
                }
            }
        `;
        document.head.appendChild(style);
        
        // More aggressive element removal via JavaScript
        const selectorsToRemove = [
            'header', 'nav', 'footer',
            '.header', '.footer', '.navigation',
            '[role="navigation"]', '[role="banner"]', '[role="contentinfo"]',
            '.subscribe-form', '.newsletter-signup',
            '.social-share', '.share-buttons'
        ];
        
        selectorsToRemove.forEach(selector => {
            document.querySelectorAll(selector).forEach(el => el.remove());
        });
        
        // Remove fixed position elements that might overlap
        document.querySelectorAll('[style*="position: fixed"]').forEach(el => el.remove());
        document.querySelectorAll('[style*="position: sticky"]').forEach(el => el.remove());
        
        // Remove specific text patterns that appear in footers
        const footerTextPatterns = [
            /ADVERTISE.*?FAQ/gi,
            /Update your email preferences/gi,
            /unsubscribe/gi,
            /View our privacy policy/gi,
            /Copyright.*?Morning Brew.*?rights reserved/gi,
            /22 W 19th St.*?10011/gi,
            /Was this email forwarded/gi,
            /Sign up here/gi
        ];
        
        // Find and remove elements containing footer text
        const allElements = document.querySelectorAll('*');
        allElements.forEach(el => {
            const text = el.innerText || el.textContent || '';
            for (let pattern of footerTextPatterns) {
                if (pattern.test(text)) {
                    // Check if this element only contains footer text
                    if (text.length < 500) {  // Footer text is usually short
                        el.remove();
                        break;
                    }
                }
            }
        });
        
        // Also try to find and remove by common footer link text
        const footerLinks = ['ADVERTISE', 'CAREERS', 'SHOP', 'FAQ', 'privacy policy', 'unsubscribe'];
        footerLinks.forEach(linkText => {
            const links = Array.from(document.querySelectorAll('a')).filter(
                a => a.textContent.includes(linkText)
            );
            links.forEach(link => {
                // Remove the parent container if it looks like a footer
                let parent = link.parentElement;
                while (parent && parent !== document.body) {
                    const parentText = parent.textContent || '';
                    if (parentText.includes('ADVERTISE') && parentText.includes('CAREERS') ||
                        parentText.includes('Copyright') ||
                        parentText.includes('email preferences')) {
                        parent.remove();
                        break;
                    }
                    parent = parent.parentElement;
                }
            });
        });
        """
        
        self.driver.execute_script(cleanup_css)
    
    def generate_pdf(self, url, title="article", wait_time=5):
        """
        Generate a clean PDF from a URL.
        
        Args:
            url: Article URL
            title: Title for the PDF filename
            wait_time: Seconds to wait for page load
            
        Returns:
            Path to generated PDF or None if failed
        """
        try:
            print(f"Loading: {url}")
            self.driver.get(url)
            
            # Wait for content to load
            time.sleep(wait_time)
            
            # Try to wait for main content
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "article"))
                )
            except:
                # Page might not have article tag
                pass
            
            # Inject cleanup CSS and JavaScript
            self.inject_cleanup_css()
            
            # Additional wait after cleanup
            time.sleep(2)
            
            # Scroll to load any lazy-loaded content
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            self.driver.execute_script("window.scrollTo(0, 0);")
            
            # Generate PDF using Chrome DevTools Protocol
            pdf_data = self.driver.execute_cdp_cmd("Page.printToPDF", {
                "landscape": False,
                "displayHeaderFooter": False,  # No headers/footers
                "printBackground": True,
                "preferCSSPageSize": True,
                "paperWidth": 8.5,
                "paperHeight": 11,
                "marginTop": 0.5,
                "marginBottom": 0.5,
                "marginLeft": 0.5,
                "marginRight": 0.5,
                "scale": 1
            })
            
            # Save PDF
            pdf_bytes = base64.b64decode(pdf_data['data'])
            
            # Clean filename
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_'))[:100]
            pdf_path = self.output_dir / f"{safe_title}.pdf"
            
            with open(pdf_path, 'wb') as f:
                f.write(pdf_bytes)
            
            print(f"  ✓ Saved: {pdf_path.name}")
            return pdf_path
            
        except Exception as e:
            print(f"  ✗ Error: {str(e)}")
            return None
    
    def process_urls(self, urls_file="output/urls_latest.json", limit=30, start_from=0):
        """
        Process URLs from saved file and generate PDFs.
        
        Args:
            urls_file: Path to JSON file with URLs
            limit: Maximum number of PDFs to generate
            start_from: Index to start from (0 = most recent)
            
        Returns:
            List of generated PDF paths
        """
        # Load URLs
        urls_file = Path(urls_file)
        if not urls_file.exists():
            print(f"URLs file not found: {urls_file}")
            return []
        
        with open(urls_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        articles = data.get('articles', [])
        
        if not articles:
            print("No articles found in URLs file")
            return []
        
        # Use articles in order they appear (already most recent first)
        # Apply start index and limit
        articles = articles[start_from:start_from + limit]
        
        print(f"\nProcessing {len(articles)} articles...")
        print("=" * 60)
        
        generated_pdfs = []
        
        for i, article in enumerate(articles, 1):
            print(f"\n[{i}/{len(articles)}] {article.get('title', 'Untitled')[:80]}")
            
            # Generate filename with date if available
            date_str = article.get('date', '').replace(',', '').replace(' ', '_')
            title = article.get('title', 'untitled')
            
            if date_str:
                filename = f"{date_str}_{title}"
            else:
                filename = f"{i:03d}_{title}"
            
            pdf_path = self.generate_pdf(
                url=article['url'],
                title=filename,
                wait_time=5
            )
            
            if pdf_path:
                generated_pdfs.append(pdf_path)
            
            # Brief pause between requests
            time.sleep(2)
        
        return generated_pdfs


def main():
    """Main execution."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate PDFs from Morning Brew URLs")
    parser.add_argument("--urls-file", default="output/urls_latest.json",
                       help="Path to URLs JSON file")
    parser.add_argument("--limit", type=int, default=30,
                       help="Maximum number of PDFs to generate (default: 30)")
    parser.add_argument("--output-dir", default="pdfs",
                       help="Directory to save PDFs")
    parser.add_argument("--start", type=int, default=0,
                       help="Start index (0 = most recent, default: 0)")
    
    args = parser.parse_args()
    
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║  Morning Brew PDF Generator                              ║
    ║  Step 2: Converting articles to clean PDFs               ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    with MorningBrewPDFGenerator(output_dir=args.output_dir) as generator:
        pdfs = generator.process_urls(
            urls_file=args.urls_file,
            limit=args.limit,
            start_from=args.start  # Now matches the function parameter name
        )
        
        print("\n" + "=" * 60)
        print(f"COMPLETE: Generated {len(pdfs)} PDFs")
        print(f"Location: {args.output_dir}/")
        
        if pdfs:
            print("\nGenerated files:")
            for pdf in pdfs[:5]:  # Show first 5
                print(f"  - {pdf.name}")
            if len(pdfs) > 5:
                print(f"  ... and {len(pdfs) - 5} more")


if __name__ == "__main__":
    main()