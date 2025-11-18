# Changelog

All notable changes to the ForexFactory Calendar Scraper will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Xvfb (X Virtual Framebuffer) support for GitHub Actions to bypass Cloudflare detection
- Entrypoint script (`entrypoint.sh`) to start virtual display before running scraper
- Sentiment data extraction from ForexFactory HTML (`actual_status`: better/worse/unchanged)
- Monthly backfill job now covers October, November, and December data

### Changed
- **BREAKING**: Realtime job now scrapes `week=this` instead of `day=today` (~118 events vs ~15)
- **BREAKING**: Daily sync job now scrapes `month=this` instead of `week=this` (~400+ events)
- **BREAKING**: Realtime job interval changed from every 15 minutes to every 5 minutes
- Replaced headless Chrome mode with Xvfb virtual display for GitHub Actions
- Improved Docker image with X11 utilities for virtual display support
- Updated Docker build workflow to fix image name lowercasing syntax error

### Fixed
- GitHub Actions scraping failure (0 events) caused by Cloudflare blocking headless Chrome
- Docker build workflow syntax error with unsupported Jinja2 filter `| lower`
- Database updates stopped since Nov 9th due to headless mode Cloudflare blocking

### Data Coverage Strategy
The new multi-layered approach ensures complete coverage:
- **Realtime (every 5 min)**: `week=this` - ~118 events, 288 runs/day
- **Daily (02:00 UTC)**: `month=this` - ~400+ events, once/day
- **Monthly backfill**: `month=last/this/next` - ~1,200+ events, as needed

### Technical Details
- Fixed Chrome driver to use virtual display (DISPLAY=:99) instead of --headless flag
- Added Xvfb, x11-utils packages to Dockerfile
- Database updates now include sentiment analysis (actual_status field)
- All CSVs now include sentiment data in exports

## [Previous Versions]

### 2025-11-09
- Initial implementation of ForexFactory scraper with semantic HTML parsing
- Database integration with PostgreSQL
- GitHub Actions workflows for automated scraping
- Docker containerization
- Timezone detection and conversion support
- UPSERT operations for efficient data updates
