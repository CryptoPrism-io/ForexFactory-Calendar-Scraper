# QT Funded Scraper - Sample Output

## Overview

This document shows examples of the data extracted by the QT Funded scraper from the three program pages.

## Scraping Summary

- **Programs Scraped**: 3 (QT Prime, QT Power, QT Instant)
- **Pages Visited**: 8
- **Total Sections Extracted**: 35+
- **Output Files**: 2 JSON files (raw + structured)

## Output Files

### 1. Raw Data (`qt_funded_raw_*.json`)
- **Size**: 65 KB
- **Lines**: 1,737
- **Contains**: Complete page content including all sections, links, tables, and related pages

### 2. Structured Rules (`qt_funded_rules_*.json`)
- **Size**: 40 KB
- **Lines**: 720
- **Contains**: Organized rules categorized by type

## Data Structure

### Programs Extracted

#### QT Prime
- **Rules**: 13 categories
- **Requirements**: 1 category
- **Account Details**: 5 categories
- **Related Pages**:
  - Responsibilities of Traders
  - Conditions of Funding
  - Prohibited Trading Strategies
  - QT News Rule
  - Performance Fee Policy

#### QT Power
- **Rules**: 6 categories
- **Account Details**: 3 categories

#### QT Instant
- **Rules**: 7 categories
- **Account Details**: 2 categories

## Sample Extracted Rules

### Example 1: News Trading Rule (QT Prime)

```json
{
  "category": "6. What is the News Trading Rule? (Funded Accounts Only)",
  "details": [
    "Red Folder news events have restrictions",
    "No opening, closing, or adjusting trades 5 minutes before or after a Red Folder news event",
    "If a predefined Stop Loss (SL) or Take Profit (TP) is hit, it will be honored",
    "Violating this rule will result in a hard breach",
    "QT PRIME ON-DEMAND DOES NOT have the news rule applied"
  ]
}
```

**How to Follow**:
- Check economic calendar for Red Folder news events
- Avoid opening/closing/adjusting trades within 5-minute window
- Pre-set SL/TP orders are acceptable

**How to Break**:
- Opening a trade 3 minutes before high-impact news
- Manually closing a position 2 minutes after news release
- Adjusting position size during the restricted window

### Example 2: Layering Rule (QT Prime)

```json
{
  "category": "7. What is the Layering Rule? (Funded Accounts Only)",
  "details": [
    "Traders cannot have three or more open positions on the same asset at the same time",
    "Violating this rule will result in a hard breach",
    "NO LAYERING RULE - For Accounts purchased or issued after the 9th of April 2025"
  ]
}
```

**How to Follow**:
- Maximum 2 open positions per asset
- Close one position before opening a third on same asset
- Note: Rule waived for accounts after April 9, 2025

**How to Break**:
- Opening 3 EUR/USD positions simultaneously
- Having 4 Gold (XAU/USD) positions open

### Example 3: Stop Loss Rule (QT Prime)

```json
{
  "category": "8. What is the Stop Loss (SL) Rule? (Funded Accounts Only)",
  "details": [
    "A Stop Loss must be placed within 60 seconds of opening a trade",
    "Failure to place a Stop Loss within 60 seconds will result in a hard breach",
    "NO STOP LOSS RULE - For Accounts purchased after the 13th of June 2025"
  ]
}
```

**How to Follow**:
- Place SL within 60 seconds of trade entry
- Can adjust SL after initial placement
- Note: Rule waived for accounts after June 13, 2025

**How to Break**:
- Opening a trade and waiting 90 seconds to set SL
- Forgetting to set SL entirely
- Closing trade before 60 seconds without setting SL (considered abusive behavior)

### Example 4: Profit Targets (QT Prime)

```json
{
  "category": "2. What are the profit targets?",
  "details": [
    "2-Step Evaluation:",
    "Stage 1: 8% Profit Target",
    "Stage 2: 5% Profit Target",
    "3-Step Evaluation:",
    "Each stage: 6% Profit Target"
  ]
}
```

### Example 5: Daily Drawdown (All Programs)

```json
{
  "category": "3. What are the drawdown limits?",
  "details": [
    "Daily drawdown: 4% fixed, based on the initial balance",
    "Maximum drawdown: 10% of initial account",
    "Optional Equity Protector: 1.5% (auto-closes positions)"
  ]
}
```

**How to Follow**:
- Monitor daily P&L relative to initial balance
- Use risk management to stay within 4% daily loss
- Set alerts at 3% daily loss as buffer
- Maximum cumulative loss cannot exceed 10%

**How to Break**:
- Losing 5% in a single day
- Cumulative account drawdown reaching 11%
- Not accounting for commissions in drawdown calculation

### Example 6: Trading Requirements

```json
{
  "category": "4. What are the minimum trading day requirements?",
  "details": [
    "Minimum 4 trading days per phase",
    "Funded traders need 2 profitable days minimum at 0.5%+ each"
  ]
}
```

**How to Follow**:
- Trade on at least 4 separate calendar days
- For funded account: Ensure 2 days are profitable at 0.5%+ each
- Days don't need to be consecutive

**How to Break**:
- Passing Stage 1 in only 3 trading days
- Having only 1 profitable day in funded account cycle

### Example 7: Leverage Limits

```json
{
  "category": "10. What leverage is provided under QT PRIME?",
  "details": [
    "Forex: 1:50",
    "Indices & Oil: 1:20",
    "Metals: 1:15",
    "Crypto: 1:1"
  ]
}
```

### Example 8: Account Management Responsibilities

```json
{
  "category": "Account Management",
  "details": [
    "Control and Ownership: You are solely responsible for managing your account",
    "Device Usage: Ensure the device used is owned by the account holder",
    "Exclusive Access: Your account is for your use only",
    "Sharing login credentials is strictly prohibited"
  ]
}
```

**How to Follow**:
- Use only your own devices
- Keep credentials private
- Don't share account access

**How to Break**:
- Sharing login credentials with another trader
- Using a shared/public computer for trading
- Letting someone else trade on your account

### Example 9: Excessive Exposure Rule

```json
{
  "category": "Simulated Funds Responsibilities",
  "details": [
    "Excessive Exposure: Those who have been found to have risked excessively i.e. risking more than 75% of their daily or max drawdown limits/lot limits within their open positions will face the penalty of having their evaluations reset to phase 1"
  ]
}
```

**How to Follow**:
- Keep risk per trade reasonable (e.g., 1-2% of account)
- Don't risk close to maximum drawdown limits
- Use proper position sizing

**How to Break**:
- Opening a position that risks 3% when you have 4% daily drawdown remaining
- Using excessive lot sizes that would breach limits on slight movement

## Categories of Rules Extracted

### 1. Trading Rules
- News trading restrictions
- Layering limitations
- Stop loss requirements
- Lot size limits
- Prohibited strategies

### 2. Account Requirements
- Profit targets by phase
- Drawdown limits (daily and maximum)
- Minimum trading days
- Funded account profitability requirements

### 3. Risk Management
- Leverage by asset class
- Exposure limits
- Equity protector options
- Commission considerations

### 4. Payout Policies
- Biweekly vs On-Demand options
- Profit split percentages
- Consistency score requirements
- Wallet address submission

### 5. Trader Responsibilities
- Account security
- Device usage
- Credential protection
- Email communication
- Accountability for all trades

## Data Quality

✅ **Successfully Extracted**:
- All main program descriptions
- Trading rules and restrictions
- Account specifications
- Payout policies
- Risk management guidelines
- Trader responsibilities

✅ **Hyperlink Following**:
- Related pages automatically discovered and scraped
- Cross-references resolved
- Additional details captured from linked pages

✅ **Structured Format**:
- Rules categorized by type
- Easy-to-parse JSON structure
- Both raw and processed versions available

## Usage Examples

### Finding Specific Rules

```python
import json

# Load structured rules
with open('qt_funded_rules_20251114_190704.json', 'r') as f:
    data = json.load(f)

# Get all QT Prime rules
qt_prime = data['programs']['qt-prime']

# Find news trading rules
for rule in qt_prime['rules']:
    if 'news' in rule['category'].lower():
        print(rule)

# Get all prohibited strategies
prohibited = qt_prime['prohibited']
print(f"Found {len(prohibited)} prohibited strategy categories")
```

### Comparing Programs

```python
# Compare profit targets across programs
for program_name, program_data in data['programs'].items():
    print(f"\n{program_name.upper()}:")
    for detail in program_data['account_details']:
        if 'profit' in detail['category'].lower():
            print(f"  {detail['category']}")
            for item in detail['details']:
                print(f"    - {item}")
```

## Notes

- All times are scraped as displayed on the website
- Rules may vary by account purchase date (noted in details)
- Some programs have rule waivers after specific dates
- Cross-references between pages are preserved
- Tables are extracted with headers and rows

## Files Location

```
qt_funded_scraper/
├── data/
│   ├── qt_funded_raw_20251114_190704.json      # Complete raw data
│   └── qt_funded_rules_20251114_190704.json    # Structured rules
├── qt_scraper_simple.py                         # Main scraper script
└── README.md                                     # Documentation
```

---

**Last Updated**: 2025-11-14
**Scraper Version**: 1.0
**Pages Scraped**: 8 (3 main + 5 related)
