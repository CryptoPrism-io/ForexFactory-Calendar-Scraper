#!/bin/bash
#
# Test runner for ForexFactory Scraper
# Runs timezone verification tests
#

set -e

echo "========================================"
echo "ForexFactory Scraper - Test Suite"
echo "========================================"
echo ""

# Navigate to script directory
cd "$(dirname "$0")"

echo "Running timezone verification tests..."
echo ""

# Run tests with unittest
python -m unittest discover -s tests -p "test_*.py" -v

echo ""
echo "========================================"
echo "All tests passed!"
echo "========================================"
