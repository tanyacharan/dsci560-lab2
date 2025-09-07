"""
Morning Brew Archive URL Scraper
=================================
Gets all article URLs by clicking "Load More" repeatedly.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup

# Import webdriver_manager (should be installed now)
try:
    from webdriver_manager.chrome import ChromeDriverManager
    DRIVER_MANAGER_AVAILABLE = True
except ImportError:
    DRIVER_MANAGER_AVAILABLE = False
    print("Warning: webdriver-manager not found")


def scrape_morning_brew_urls(headless=False, max_clicks=100):
    """
    Scrape all article URLs from Morning Brew archive.
    
    Args:
        headless: Run without browser window
        max_clicks: Maximum number of "Load More" clicks
        
    Returns:
        List of article dictionaries
    """
    # Setup Chrome options
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    
    from selenium.webdriver.chrome.service import Service
    import os
    
    # Look for chromedriver in current directory
    chromedriver_path = "./chromedriver.exe"
    
    if os.path.exists(chromedriver_path):
        service = Service(executable_path=chromedriver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
    else:
        print("Please download chromedriver.exe and put it in this folder")
        print("Download from: https://googlechromelabs.github.io/chrome-for-testing/")
        return []
    
    if not driver:
        raise Exception("Could not create Chrome driver. Try updating Selenium: pip install --upgrade selenium")
    
    try:
        # Navigate to archive
        print("Loading Morning Brew archive...")
        driver.get("https://www.morningbrew.com/archive")
        time.sleep(5)  # Let initial content load
        
        articles = []
        seen_urls = set()
        click_count = 0
        
        while click_count < max_clicks:
            # Parse current page
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            # Find all article links - multiple selectors for different formats
            link_selectors = [
                'a[href*="/issues/"]',
                'a[href*="/daily/"]', 
                'article a[href]',
                'div[class*="issue"] a',
                'div[class*="post"] a'
            ]
            
            for selector in link_selectors:
                for link in soup.select(selector):
                    href = link.get('href', '')
                    
                    # Skip invalid links
                    if not href or href == '#' or '/archive' in href:
                        continue
                    
                    full_url = urljoin("https://www.morningbrew.com", href) # type: ignore
                    
                    # Skip generic newsletter links and UTM links
                    skip_patterns = [
                        '/issues/latest',
                        'utm_medium=',
                        'utm_source=',
                        'utm_campaign=',
                        '/subscribe',
                        '/unsubscribe',
                        '/preferences'
                    ]
                    
                    if any(pattern in full_url for pattern in skip_patterns):
                        continue
                    
                    # Skip duplicates
                    if full_url in seen_urls:
                        continue
                    
                    # Extract title
                    title = link.get_text(strip=True) or "Untitled"
                    
                    # Try to find date
                    date_str = ""
                    parent = link.parent
                    depth = 0
                    while parent and not date_str and depth < 5:
                        text = parent.get_text()
                        # Look for month names
                        months = ['January', 'February', 'March', 'April', 'May', 'June',
                                'July', 'August', 'September', 'October', 'November', 'December']
                        for month in months:
                            if month in text:
                                import re
                                date_pattern = rf'({month}\s+\d{{1,2}},?\s+\d{{4}})'
                                date_match = re.search(date_pattern, text)
                                if date_match:
                                    date_str = date_match.group(1)
                                    break
                        parent = parent.parent
                        depth += 1
                    
                    # Add article
                    articles.append({
                        'url': full_url,
                        'title': title[:200],
                        'date': date_str,
                        'scraped_at': datetime.now().isoformat()
                    })
                    seen_urls.add(full_url)
            
            print(f"Articles found: {len(articles)}")
            
            # Try to click "Load More"
            try:
                # Multiple possible button selectors
                button_xpaths = [
                    "//button[contains(text(), 'Load More')]",
                    "//button[contains(., 'Load More Results')]",
                    "//button[contains(@class, 'btn') and contains(., 'Load More')]"
                ]
                
                load_more = None
                for xpath in button_xpaths:
                    try:
                        load_more = WebDriverWait(driver, 3).until(
                            EC.element_to_be_clickable((By.XPATH, xpath))
                        )
                        break
                    except:
                        continue
                
                if not load_more:
                    print("No 'Load More' button found - reached end")
                    break
                
                # Scroll to button
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", load_more)
                time.sleep(1)
                
                # Click using JavaScript to avoid interception
                driver.execute_script("arguments[0].click();", load_more)
                click_count += 1
                print(f"Clicked 'Load More' ({click_count}/{max_clicks})")
                
                # Wait for new content
                time.sleep(7)
                
            except (TimeoutException, NoSuchElementException):
                print("No more content to load!")
                break
        
        return articles
        
    finally:
        driver.quit()
        print("Browser closed")


def save_urls(articles, output_dir="output"):
    """Save scraped URLs to files."""
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save JSON with all data
    json_file = output_dir / f"morning_brew_urls_{timestamp}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump({
            'scrape_date': datetime.now().isoformat(),
            'total': len(articles),
            'articles': articles
        }, f, indent=2, ensure_ascii=False)
    
    # Save simple URL list
    txt_file = output_dir / "urls_only.txt"
    with open(txt_file, 'w', encoding='utf-8') as f:
        for article in articles:
            f.write(f"{article['url']}\n")
    
    # Save as latest
    latest_file = output_dir / "urls_latest.json"
    with open(latest_file, 'w', encoding='utf-8') as f:
        json.dump({
            'scrape_date': datetime.now().isoformat(),
            'total': len(articles),
            'articles': articles
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\nSaved {len(articles)} URLs to:")
    print(f"  - {json_file}")
    print(f"  - {txt_file}")
    print(f"  - {latest_file}")
    
    return json_file


def main():
    """Main execution."""
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║  Morning Brew Archive URL Scraper                       ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    # Scrape URLs
    print("\nStarting scrape...")
    articles = scrape_morning_brew_urls(
        headless=False,  # Set to True to hide browser
        max_clicks=100   # Adjust as needed
    )
    
    if articles:
        # Save results
        save_urls(articles)
        
        # Print summary
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        print(f"Total articles: {len(articles)}")
        
        if articles:
            print(f"First: {articles[0]['title']}")
            print(f"Last: {articles[-1]['title']}")
            
            # Date range
            dates = [a['date'] for a in articles if a['date']]
            if dates:
                print(f"Date range: {min(dates)} to {max(dates)}")
    else:
        print("No articles found!")


if __name__ == "__main__":
    main()