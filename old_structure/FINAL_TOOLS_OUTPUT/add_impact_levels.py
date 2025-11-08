#!/usr/bin/env python3
"""
Add Impact Levels to ForexFactory Events Based on Event Title
Maps event titles to their typical impact levels:
  High (Red) = Major economic indicators with high market impact
  Medium (Orange) = Secondary indicators with moderate impact
  Low (Yellow) = Minor indicators with low impact
"""

import pandas as pd
import re
from pathlib import Path

# ForexFactory Impact Classification Rules
# Based on historical ForexFactory calendar impact levels
IMPACT_MAPPING = {
    # ===== HIGH IMPACT (RED) =====
    'high': [
        # Central Bank
        'FOMC', 'Fed', 'ECB', 'BOE', 'BOJ', 'RBNZ', 'RBA', 'BoC',
        'Interest Rate', 'Rate Decision', 'Monetary Policy',
        'Central Bank',

        # Employment (Very High Impact)
        'Nonfarm Payroll', 'Employment Change', 'Jobless Claims',
        'Unemployment Rate', 'Initial Claims', 'Continuing Claims',
        'ADP Employment', 'Employment Report',

        # GDP (Very High Impact)
        'GDP', 'Gross Domestic Product',

        # Inflation (Very High Impact)
        'CPI', 'Consumer Price Index', 'Core CPI', 'PCE', 'PPI',
        'Producer Price Index', 'Inflation Rate',

        # Major Trade
        'Trade Balance', 'Exports', 'Imports', 'Trade Deficit',

        # Retail Sales (High Impact)
        'Retail Sales', 'Core Retail', 'Advanced Retail',

        # Housing (High Impact)
        'Housing Starts', 'Building Permits', 'New Home Sales',
        'Existing Home Sales', 'Housing Data',

        # Industrial Production
        'Industrial Production', 'Capacity Utilization',

        # Consumer Confidence (High Impact for some)
        'Consumer Confidence', 'Consumer Sentiment',
        'Conference Board', 'University of Michigan',

        # Durable Goods
        'Durable Goods Orders', 'Core Durable Goods',

        # Financial Stability
        'Financial Stability Report',
    ],

    # ===== MEDIUM IMPACT (ORANGE) =====
    'medium': [
        # PMI (Important but secondary)
        'PMI', 'Purchasing Managers Index', 'Markit', 'Flash PMI',
        'Manufacturing PMI', 'Services PMI', 'Composite PMI',

        # Building/Construction
        'Building Permits', 'Construction', 'Building Approvals',
        'Building Consents', 'Permits',

        # Factory Orders
        'Factory Orders', 'Orders', 'Business Orders',

        # Consumer Spending
        'Consumer Spending', 'Personal Spending', 'Personal Income',
        'Disposable Income', 'Household Spending',

        # Inflation Expectations
        'Inflation Expectations', 'Expected Inflation',

        # ISM
        'ISM', 'ISM Non-Manufacturing', 'ISM Manufacturing',

        # Wages
        'Average Hourly Earnings', 'Wage Growth', 'Wage Rate',
        'Wage', 'Earnings',

        # Business Surveys
        'Business Confidence', 'Business Climate',
        'Economic Surprise Index',

        # Reserve Assets
        'Foreign Reserves', 'Currency Reserves', 'Reserve Assets',

        # Credit
        'Consumer Credit', 'Credit Growth',

        # Commodity
        'Commodity Prices', 'Raw Materials',
    ],

    # ===== LOW IMPACT (YELLOW) =====
    'low': [
        # Speeches (usually low impact unless special)
        'Speaks', 'Speech', 'Speaking Engagement', 'Conference',
        'Testimony', 'Discussion Panel',

        # Holidays
        'Holiday', 'Market Holiday', 'Bank Holiday',
        'New Year', 'Christmas', 'Easter', 'Thanksgiving',

        # Technical/System Events
        'Daylight Saving', 'Summer Time', 'Winter Time',
        'Market Close', 'Market Open', 'Half Day',

        # Regional/Secondary Indicators
        'Regional', 'State', 'Territory',

        # Inflation Gauge (secondary)
        'Inflation Gauge',

        # Sentiment Surveys
        'Sentiment', 'Survey', 'Opinion',

        # Secondary Services
        'Services', 'Services Activity',

        # General
        'Preliminary', 'Advanced', 'Flash',
    ]
}


def classify_impact(event_title):
    """
    Classify event impact based on title
    Returns: 'high', 'medium', or 'low'
    """
    if not event_title or pd.isna(event_title):
        return 'unknown'

    title_lower = str(event_title).lower()

    # Check HIGH impact first (most important)
    for pattern in IMPACT_MAPPING['high']:
        if pattern.lower() in title_lower:
            return 'high'

    # Check MEDIUM impact
    for pattern in IMPACT_MAPPING['medium']:
        if pattern.lower() in title_lower:
            return 'medium'

    # Check LOW impact
    for pattern in IMPACT_MAPPING['low']:
        if pattern.lower() in title_lower:
            return 'low'

    # Default to unknown if no match
    return 'unknown'


def add_impact_to_csv(input_csv, output_csv):
    """Add impact levels to CSV based on event titles"""

    print(f"Reading: {input_csv}")
    df = pd.read_csv(input_csv)

    print(f"Records loaded: {len(df)}")

    # Apply impact classification
    print("\nClassifying impact levels based on event titles...")
    df['Impact'] = df['Event'].apply(classify_impact)

    # Save to new CSV
    Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_csv, index=False, encoding='utf-8')

    print(f"\n✓ Saved to: {output_csv}")

    # Show summary
    print(f"\n{'='*70}")
    print("IMPACT CLASSIFICATION SUMMARY")
    print(f"{'='*70}")
    print(f"\nTotal Events: {len(df)}")
    print(f"\nImpact Distribution:")

    impact_dist = df['Impact'].value_counts().sort_values(ascending=False)
    for impact, count in impact_dist.items():
        pct = (count / len(df)) * 100
        emoji = {'high': '🔴', 'medium': '🟠', 'low': '🟡', 'unknown': '⚪'}.get(impact, '?')
        print(f"  {emoji} {impact.upper():10} {count:4} ({pct:5.1f}%)")

    print(f"\nSample Events by Impact:")
    for impact in ['high', 'medium', 'low']:
        if impact in df['Impact'].values:
            print(f"\n  {impact.upper()}:")
            sample = df[df['Impact'] == impact]['Event'].head(3).values
            for event in sample:
                print(f"    • {event}")

    print(f"\n{'='*70}\n")

    return df


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Add Impact Levels to ForexFactory Events CSV"
    )
    parser.add_argument(
        '--input',
        default='forexfactory_events.csv',
        help='Input CSV file (default: forexfactory_events.csv)'
    )
    parser.add_argument(
        '--output',
        default='forexfactory_events_with_impact.csv',
        help='Output CSV file (default: forexfactory_events_with_impact.csv)'
    )

    args = parser.parse_args()

    print("="*70)
    print("ForexFactory Impact Level Classifier")
    print("="*70 + "\n")

    if not Path(args.input).exists():
        print(f"Error: {args.input} not found!")
        return 1

    df = add_impact_to_csv(args.input, args.output)
    print(f"✓ Classification complete!")
    print(f"✓ Output: {args.output}")

    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
