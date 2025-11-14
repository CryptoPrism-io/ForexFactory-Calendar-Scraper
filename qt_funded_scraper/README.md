# QT Funded Prop Firm Rules Scraper

A comprehensive web scraper for extracting prop firm rules, requirements, and trading policies from QT Funded help center pages.

## Overview

This scraper automatically extracts detailed information from QT Funded's three main trading programs:
- **QT Prime** - 2-Step and 3-Step evaluation programs
- **QT Power** - Alternative evaluation structure
- **QT Instant** - Instant funding options

## Features

✅ **Intelligent Content Extraction**: Automatically filters out headers, footers, and navigation
✅ **Hyperlink Following**: Discovers and scrapes related pages for comprehensive rule coverage
✅ **Structured Data**: Organizes rules into categories (prohibited, requirements, compliance, violations)
✅ **JSON Export**: Outputs both raw and structured JSON data
✅ **Cloudflare Bypass**: Uses undetected-chromedriver to bypass anti-bot protections
✅ **Smart Categorization**: Automatically categorizes rules based on content and headings

## Output Format

The scraper generates two JSON files:

### 1. Raw Data (`qt_funded_raw_*.json`)
Complete page content including:
- Page titles and URLs
- All sections with headings and content
- Tables, lists, and paragraphs
- Internal links discovered
- Related pages content

### 2. Structured Rules (`qt_funded_rules_*.json`)
Organized rule information:
```json
{
  "programs": {
    "qt-prime": {
      "name": "qt-prime",
      "title": "QT PRIME",
      "url": "https://qtfunded.kb.help/qt-prime/",
      "rules": [
        {
          "category": "Trading Rules",
          "details": ["Rule description...", "..."]
        }
      ],
      "requirements": [...],
      "prohibited": [...],
      "compliance_examples": [...],
      "violation_examples": [...]
    }
  }
}
```

## Installation

1. **Navigate to the scraper directory**:
   ```bash
   cd qt_funded_scraper
   ```

2. **Install dependencies** (uses parent directory requirements):
   ```bash
   pip install -r ../scraper_2.2/requirements.txt
   ```

3. **Verify Chrome is installed** (required for undetected-chromedriver)

## Usage

### Basic Usage

Run the scraper to collect all QT Funded rules:

```bash
python qt_scraper.py
```

The scraper will:
1. Visit each of the three main program pages
2. Extract all content sections
3. Follow internal hyperlinks to gather detailed rules
4. Filter out navigation, headers, and footers
5. Categorize rules into structured format
6. Save both raw and structured JSON outputs

### Output Location

All output files are saved to the `data/` directory:
- `qt_funded_raw_YYYYMMDD_HHMMSS.json` - Complete raw data
- `qt_funded_rules_YYYYMMDD_HHMMSS.json` - Structured rules

## Data Structure

### Categories

The scraper automatically categorizes content into:

- **Rules**: General trading rules and policies
- **Requirements**: Minimum requirements and mandatory conditions
- **Prohibited**: Prohibited strategies and restricted actions
- **Compliance Examples**: Examples of proper rule following
- **Violation Examples**: Examples of rule violations

### Content Types

Extracted content includes:
- **Paragraphs**: Text descriptions
- **Lists**: Bulleted or numbered items
- **Tables**: Structured data (account sizes, profit targets, etc.)

## Configuration

### Adjustable Parameters

Edit `qt_scraper.py` to customize:

```python
# Maximum depth for following links (default: 1)
max_depth = 1

# Number of links to follow per page (default: 10)
links_to_follow = 10

# Output directory (default: "data")
output_dir = "data"
```

### Main URLs

The scraper targets these pages by default:
```python
self.main_urls = {
    "qt-prime": "https://qtfunded.kb.help/qt-prime/",
    "qt-power": "https://qtfunded.kb.help/qt-power/",
    "qt-instant": "https://qtfunded.kb.help/qt-instant/"
}
```

## How It Works

1. **Page Loading**: Uses undetected-chromedriver to bypass Cloudflare
2. **Content Extraction**: BeautifulSoup parses HTML and filters main content
3. **Section Processing**: Identifies headings and associated content
4. **Link Discovery**: Finds internal help center links
5. **Recursive Scraping**: Follows links to related pages (configurable depth)
6. **Categorization**: Organizes content based on keywords and structure
7. **JSON Export**: Saves both raw and processed data

## Filtering Logic

The scraper automatically excludes:
- Header and footer elements
- Navigation menus
- Breadcrumbs
- Social media links
- External links (non-qtfunded.kb.help)
- Login/signup pages
- Search functionality

## Example Output

### Extracted Rules Example
```json
{
  "category": "News Trading Rule",
  "details": [
    "No trades allowed 5 minutes before or after Red Folder news events",
    "Applies only to funded accounts",
    "Check economic calendar for high-impact events"
  ]
}
```

### Prohibited Strategies Example
```json
{
  "category": "Prohibited Trading Strategies",
  "source": "Trading Policy",
  "details": [
    "All-or-nothing approach prohibited on funded accounts",
    "Maximum 2.5% account exposure at any time",
    "Layering rule: Maximum 2 positions per asset"
  ]
}
```

## Troubleshooting

### Chrome Driver Issues
If you encounter driver errors:
```bash
# Update Chrome to latest version
# Or specify Chrome version in code:
driver = uc.Chrome(version_main=120)  # Use your Chrome version
```

### Missing Content
If content appears incomplete:
- Increase wait times in `scrape_page()` method
- Check if page structure has changed
- Review browser console for JavaScript errors

### Too Many Links
If scraping takes too long:
- Reduce `max_depth` parameter (default: 1)
- Limit links per page (default: 10)
- Focus on specific programs only

## Performance

- **Scraping Time**: ~2-5 minutes for all three programs
- **Pages Visited**: 10-30 pages depending on link depth
- **Output Size**: 100KB - 1MB per JSON file
- **Memory Usage**: ~200-400 MB

## Future Enhancements

Potential improvements:
- [ ] Add filtering for specific rule types
- [ ] Export to CSV/Excel format
- [ ] Compare rules between programs
- [ ] Track rule changes over time
- [ ] Add PostgreSQL database storage
- [ ] Schedule automated scraping

## Dependencies

Uses the same dependencies as the main ForexFactory scraper:
- `selenium>=4.15.0`
- `undetected-chromedriver>=3.5.4`
- `beautifulsoup4>=4.12.0`

See `../scraper_2.2/requirements.txt` for complete list.

## License

Same license as parent ForexFactory Calendar Scraper project.

## Related Projects

- **ForexFactory Scraper**: Parent project for economic calendar data
- Located in: `../scraper_2.2/`

---

**Built with the same architecture as ForexFactory Calendar Scraper**
