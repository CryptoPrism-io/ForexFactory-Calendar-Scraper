#!/usr/bin/env python3
"""
QT Funded Prop Firm Rules Scraper
Scrapes prop firm rules from QT Funded help center pages
Extracts rules, examples, and compliance information
"""

import time
import json
import re
import logging
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from bs4 import BeautifulSoup
except ImportError:
    raise ImportError("Missing required packages. Install with: pip install -r ../scraper_2.2/requirements.txt")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class QTFundedScraper:
    """Scraper for QT Funded prop firm rules and documentation"""

    def __init__(self, output_dir="data"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.visited_urls = set()
        self.all_data = {}
        self.driver = None

        # Main pages to scrape
        self.main_urls = {
            "qt-prime": "https://qtfunded.kb.help/qt-prime/",
            "qt-power": "https://qtfunded.kb.help/qt-power/",
            "qt-instant": "https://qtfunded.kb.help/qt-instant/"
        }

    def get_driver(self):
        """Create undetected Chrome driver"""
        import os

        options = uc.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-plugins")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

        # Add headless mode for CI/CD environments
        if os.getenv('CI') or os.getenv('GITHUB_ACTIONS'):
            options.add_argument("--headless=new")
            logger.info("Running in headless mode (CI/CD detected)")

        try:
            driver = uc.Chrome(options=options, version_main=None, use_subprocess=False)
            logger.info("Chrome driver created successfully")
            return driver
        except Exception as e:
            logger.error(f"Failed to create driver: {e}")
            return None

    def is_internal_link(self, url, base_domain="qtfunded.kb.help"):
        """Check if URL is an internal link to the same domain"""
        parsed = urlparse(url)
        return base_domain in parsed.netloc or not parsed.netloc

    def should_skip_url(self, url):
        """Check if URL should be skipped (footer, external, etc.)"""
        skip_patterns = [
            'qtfunded.com',  # External main site
            'facebook.com',
            'twitter.com',
            'linkedin.com',
            'instagram.com',
            'youtube.com',
            '#',  # Anchor links
            'javascript:',
            'mailto:',
            '/search',
            '/login',
            '/signup',
        ]

        url_lower = url.lower()
        return any(pattern in url_lower for pattern in skip_patterns)

    def extract_content_sections(self, soup):
        """Extract main content sections, filtering out header/footer"""
        content_data = {
            'title': '',
            'sections': [],
            'rules': [],
            'requirements': [],
            'links': []
        }

        # Extract title
        title_elem = soup.find('h1')
        if title_elem:
            content_data['title'] = title_elem.get_text(strip=True)

        # Find main content area (usually in article or main tag)
        main_content = soup.find('article') or soup.find('main') or soup.find('div', class_=re.compile(r'content|article|body'))

        if not main_content:
            # Fallback: try to find content by common class names
            main_content = soup.find('div', class_=re.compile(r'kb-article|help-article|documentation'))

        if not main_content:
            logger.warning("Could not find main content area, using body")
            main_content = soup.find('body')

        # Remove header and footer from main content
        for tag in main_content.find_all(['header', 'footer', 'nav']):
            tag.decompose()

        # Remove navigation, breadcrumbs, and other non-content elements
        for class_pattern in ['navigation', 'breadcrumb', 'sidebar', 'footer', 'header', 'menu']:
            for elem in main_content.find_all(class_=re.compile(class_pattern, re.I)):
                elem.decompose()

        # Extract sections
        current_section = None
        for elem in main_content.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'ul', 'ol', 'table', 'div']):
            # Skip if element is empty or just whitespace
            text = elem.get_text(strip=True)
            if not text:
                continue

            # Check if it's a heading
            if elem.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                if current_section:
                    content_data['sections'].append(current_section)

                current_section = {
                    'heading': text,
                    'level': elem.name,
                    'content': []
                }

            # Add content to current section
            elif current_section is not None:
                if elem.name == 'p':
                    current_section['content'].append({
                        'type': 'paragraph',
                        'text': text
                    })
                elif elem.name in ['ul', 'ol']:
                    items = [li.get_text(strip=True) for li in elem.find_all('li')]
                    current_section['content'].append({
                        'type': 'list',
                        'items': items
                    })
                elif elem.name == 'table':
                    # Extract table data
                    table_data = self.extract_table(elem)
                    if table_data:
                        current_section['content'].append({
                            'type': 'table',
                            'data': table_data
                        })

        # Add last section
        if current_section:
            content_data['sections'].append(current_section)

        # Extract rules (looking for keywords)
        rule_keywords = ['rule', 'requirement', 'must', 'prohibited', 'not allowed', 'restriction']
        for section in content_data['sections']:
            heading = section['heading'].lower()
            if any(keyword in heading for keyword in rule_keywords):
                content_data['rules'].append(section)

        # Extract internal links
        for link in main_content.find_all('a', href=True):
            href = link['href']
            link_text = link.get_text(strip=True)

            if not href or not link_text:
                continue

            # Convert to absolute URL
            absolute_url = urljoin(str(soup.find('base')['href']) if soup.find('base') else '', href)

            if self.is_internal_link(absolute_url) and not self.should_skip_url(absolute_url):
                content_data['links'].append({
                    'text': link_text,
                    'url': absolute_url
                })

        return content_data

    def extract_table(self, table_elem):
        """Extract data from HTML table"""
        table_data = {
            'headers': [],
            'rows': []
        }

        # Extract headers
        thead = table_elem.find('thead')
        if thead:
            header_row = thead.find('tr')
            if header_row:
                table_data['headers'] = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]

        # Extract rows
        tbody = table_elem.find('tbody') or table_elem
        for row in tbody.find_all('tr'):
            cells = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
            if cells:  # Only add non-empty rows
                table_data['rows'].append(cells)

        return table_data if (table_data['headers'] or table_data['rows']) else None

    def scrape_page(self, url, depth=0, max_depth=2):
        """Scrape a single page and optionally follow links"""
        if url in self.visited_urls or depth > max_depth:
            return None

        if self.should_skip_url(url):
            return None

        self.visited_urls.add(url)
        logger.info(f"{'  ' * depth}Scraping: {url}")

        try:
            self.driver.get(url)
            time.sleep(2)  # Wait for page load

            # Wait for main content
            try:
                WebDriverWait(self.driver, 10).until(
                    lambda d: len(d.find_elements(By.TAG_NAME, "article")) > 0 or
                              len(d.find_elements(By.TAG_NAME, "main")) > 0 or
                              "loading" not in d.page_source.lower()
                )
            except Exception as e:
                logger.warning(f"Timeout waiting for content: {e}")

            time.sleep(1)

            # Parse HTML
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            # Extract content
            page_data = self.extract_content_sections(soup)
            page_data['url'] = url
            page_data['scraped_at'] = datetime.now().isoformat()

            # Follow internal links if not at max depth
            if depth < max_depth:
                page_data['related_pages'] = []

                for link_info in page_data.get('links', [])[:10]:  # Limit to first 10 links to avoid excessive crawling
                    link_url = link_info['url']

                    if link_url not in self.visited_urls:
                        logger.info(f"{'  ' * (depth + 1)}Following link: {link_info['text']}")
                        related_data = self.scrape_page(link_url, depth + 1, max_depth)

                        if related_data:
                            page_data['related_pages'].append(related_data)

                        time.sleep(1)  # Be polite

            return page_data

        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return None

    def extract_rules_structured(self, all_pages_data):
        """Post-process scraped data to extract structured rules information"""
        structured_rules = {
            'programs': {},
            'scraped_at': datetime.now().isoformat()
        }

        for program_name, page_data in all_pages_data.items():
            program_rules = {
                'name': program_name,
                'title': page_data.get('title', ''),
                'url': page_data.get('url', ''),
                'rules': [],
                'requirements': [],
                'prohibited': [],
                'compliance_examples': [],
                'violation_examples': []
            }

            # Process sections to extract rules
            for section in page_data.get('sections', []):
                heading = section['heading'].lower()

                # Categorize based on heading
                rule_entry = {
                    'category': section['heading'],
                    'details': []
                }

                for content in section.get('content', []):
                    if content['type'] == 'paragraph':
                        rule_entry['details'].append(content['text'])
                    elif content['type'] == 'list':
                        rule_entry['details'].extend(content['items'])
                    elif content['type'] == 'table':
                        rule_entry['table'] = content['data']

                # Categorize rules
                if 'prohibited' in heading or 'not allowed' in heading or 'restriction' in heading:
                    program_rules['prohibited'].append(rule_entry)
                elif 'requirement' in heading or 'must' in heading or 'minimum' in heading:
                    program_rules['requirements'].append(rule_entry)
                elif 'rule' in heading or 'policy' in heading:
                    program_rules['rules'].append(rule_entry)
                elif 'example' in heading:
                    if 'violation' in heading or 'break' in heading:
                        program_rules['violation_examples'].append(rule_entry)
                    else:
                        program_rules['compliance_examples'].append(rule_entry)

            # Process related pages
            for related in page_data.get('related_pages', []):
                related_category = {
                    'source': related.get('title', 'Unknown'),
                    'url': related.get('url', ''),
                    'details': []
                }

                for section in related.get('sections', []):
                    for content in section.get('content', []):
                        if content['type'] == 'paragraph':
                            related_category['details'].append(content['text'])
                        elif content['type'] == 'list':
                            related_category['details'].extend(content['items'])

                # Add to appropriate category based on related page title
                title_lower = related.get('title', '').lower()
                if 'prohibited' in title_lower:
                    program_rules['prohibited'].append(related_category)
                elif 'news' in title_lower or 'rule' in title_lower:
                    program_rules['rules'].append(related_category)
                elif title_lower:
                    program_rules['rules'].append(related_category)

            structured_rules['programs'][program_name] = program_rules

        return structured_rules

    def scrape_all(self):
        """Scrape all QT Funded programs"""
        logger.info("="*70)
        logger.info("QT FUNDED PROP FIRM RULES SCRAPER")
        logger.info("="*70)
        logger.info(f"Scraping {len(self.main_urls)} programs")
        logger.info("="*70 + "\n")

        self.driver = self.get_driver()
        if not self.driver:
            logger.error("Failed to create driver")
            return False

        try:
            for program_name, url in self.main_urls.items():
                logger.info(f"\n{'='*70}")
                logger.info(f"Scraping: {program_name.upper()}")
                logger.info(f"{'='*70}")

                page_data = self.scrape_page(url, depth=0, max_depth=1)

                if page_data:
                    self.all_data[program_name] = page_data
                    logger.info(f"✓ Scraped {program_name}: {len(page_data.get('sections', []))} sections, {len(page_data.get('links', []))} links")
                else:
                    logger.error(f"✗ Failed to scrape {program_name}")

                time.sleep(2)  # Be polite between pages

            # Extract structured rules
            logger.info(f"\n{'='*70}")
            logger.info("POST-PROCESSING: Extracting Structured Rules")
            logger.info(f"{'='*70}")

            structured_data = self.extract_rules_structured(self.all_data)

            # Save raw data
            raw_output = self.output_dir / f"qt_funded_raw_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(raw_output, 'w', encoding='utf-8') as f:
                json.dump(self.all_data, f, indent=2, ensure_ascii=False)
            logger.info(f"✓ Saved raw data to: {raw_output}")

            # Save structured rules
            rules_output = self.output_dir / f"qt_funded_rules_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(rules_output, 'w', encoding='utf-8') as f:
                json.dump(structured_data, f, indent=2, ensure_ascii=False)
            logger.info(f"✓ Saved structured rules to: {rules_output}")

            # Print summary
            logger.info(f"\n{'='*70}")
            logger.info("SCRAPING SUMMARY")
            logger.info(f"{'='*70}")
            logger.info(f"Programs scraped: {len(self.all_data)}")
            logger.info(f"Pages visited: {len(self.visited_urls)}")
            logger.info(f"Output directory: {self.output_dir.absolute()}")
            logger.info(f"{'='*70}\n")

            return True

        except Exception as e:
            logger.error(f"Error during scraping: {e}")
            import traceback
            traceback.print_exc()
            return False

        finally:
            if self.driver:
                try:
                    self.driver.quit()
                    logger.info("Driver closed successfully")
                except:
                    pass


def main():
    """Main entry point"""
    scraper = QTFundedScraper(output_dir="data")
    success = scraper.scrape_all()

    if success:
        logger.info("\n✓ Scraping completed successfully!")
        return 0
    else:
        logger.error("\n✗ Scraping failed!")
        return 1


if __name__ == "__main__":
    exit(main())
