#!/usr/bin/env python3
"""
Script to fetch stock prices (WTI and IBIT) and display them for manual entry.
Does NOT modify the ODS file - displays values for you to copy/paste.
"""

import json
import yfinance as yf
from datetime import datetime
from pathlib import Path
import subprocess


def load_config():
    """Load configuration from config.json (or config.local.json if it exists)."""
    base_dir = Path(__file__).parent
    
    # Check for local config first (takes precedence, not tracked in git)
    local_config_path = base_dir / "config.local.json"
    config_path = base_dir / "config.json"
    
    if local_config_path.exists():
        with open(local_config_path, 'r') as f:
            return json.load(f)
    
    if not config_path.exists():
        default_config = {
            "ods_file_path": str(base_dir / "Dividends JRS macro.ods"),
            "sheet_name": "Journal",
            "columns": {
                "date_column": "A",
                "wti_column": "AF",
                "ibit_column": "AG"
            },
            "tickers": {
                "WTI": "CL=F",
                "IBIT": "IBIT"
            }
        }
        with open(config_path, 'w') as f:
            json.dump(default_config, f, indent=2)
        return default_config
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    return config


def get_closing_prices(tickers_config):
    """Fetch today's closing prices for configured tickers."""
    prices = {}
    
    for name, ticker in tickers_config.items():
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period='5d')  # Get last 5 days to ensure we have data
            
            if not hist.empty:
                # Get the most recent closing price
                latest_close = hist['Close'].iloc[-1]
                prices[name] = round(latest_close, 2)
            else:
                prices[name] = None
                
        except Exception as e:
            print(f"Error fetching {name} ({ticker}): {e}")
            prices[name] = None
    
    return prices


def copy_to_clipboard(text):
    """Copy text to clipboard using xclip."""
    try:
        subprocess.run(['xclip', '-selection', 'clipboard'], 
                      input=text.encode('utf-8'), 
                      check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def main():
    """Main function to fetch and display stock prices."""
    # Load configuration
    config = load_config()
    
    today = datetime.now().date()
    
    print(f"Fetching stock prices for {today}...")
    
    # Fetch closing prices
    prices = get_closing_prices(config['tickers'])
    
    # Check if we got any prices
    if all(p is None for p in prices.values()):
        print("Error: Could not fetch any stock prices.")
        return
    
    # Display prices
    print("\nPrices:")
    for name, price in prices.items():
        if price is not None:
            print(f"  {name}: ${price:.2f}")
        else:
            print(f"  {name}: [NO DATA]")
    
    # Create tab-separated values for easy pasting
    values_only = []
    if prices.get('WTI') is not None:
        values_only.append(str(prices['WTI']))
    if prices.get('IBIT') is not None:
        values_only.append(str(prices['IBIT']))
    
    tab_separated = '\t'.join(values_only)
    
    # Copy to clipboard silently
    copy_to_clipboard(tab_separated)


if __name__ == "__main__":
    main()
