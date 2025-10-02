#!/usr/bin/env python3
"""
Script to update stock prices (WTI and IBIT) in Dividends JRS macro.ods
Fetches today's closing prices and updates the journal tab.
"""

import pandas as pd
import yfinance as yf
from datetime import datetime
from pathlib import Path


def get_closing_prices():
    """Fetch today's closing prices for WTI and IBIT."""
    print("Fetching stock prices...")
    
    # WTI is represented by crude oil ETF ticker (using CL=F for crude oil futures)
    # or USO for the ETF. For simplicity, using USO or checking what WTI means in context
    # IBIT is BlackRock's Bitcoin ETF
    
    tickers = {
        'WTI': 'CL=F',  # WTI Crude Oil Futures
        'IBIT': 'IBIT'   # iShares Bitcoin Trust
    }
    
    prices = {}
    
    for name, ticker in tickers.items():
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period='5d')  # Get last 5 days to ensure we have data
            
            if not hist.empty:
                # Get the most recent closing price
                latest_close = hist['Close'].iloc[-1]
                prices[name] = round(latest_close, 2)
                print(f"{name} ({ticker}): ${latest_close:.2f}")
            else:
                print(f"Warning: No data available for {name} ({ticker})")
                prices[name] = None
                
        except Exception as e:
            print(f"Error fetching {name} ({ticker}): {e}")
            prices[name] = None
    
    return prices


def update_spreadsheet(file_path, prices):
    """Update the ODS file with today's prices."""
    print(f"\nOpening spreadsheet: {file_path}")
    
    # Read the 'journal' sheet
    df = pd.read_excel(file_path, sheet_name='journal', engine='odf')
    
    # Get today's date (formatted to match the spreadsheet format)
    today = datetime.now().date()
    
    # Convert column A to datetime for comparison (handle various date formats)
    df.iloc[:, 0] = pd.to_datetime(df.iloc[:, 0], errors='coerce')
    
    # Find if today's date exists in column A
    date_match = df.iloc[:, 0] == pd.Timestamp(today)
    
    if date_match.any():
        # Date exists, find the row index
        row_idx = date_match.idxmax()
        print(f"Found date {today} at row {row_idx + 2}")  # +2 for Excel row (1-indexed + header)
    else:
        # Date doesn't exist, insert a new row
        print(f"Date {today} not found. Adding new row...")
        
        # Find the last non-empty row in column A
        last_valid_idx = df.iloc[:, 0].last_valid_index()
        
        if last_valid_idx is not None:
            row_idx = last_valid_idx + 1
        else:
            row_idx = 0
        
        # Insert new row with today's date
        new_row = pd.Series([pd.Timestamp(today)] + [None] * (len(df.columns) - 1), 
                           index=df.columns)
        df = pd.concat([df.iloc[:row_idx], 
                       pd.DataFrame([new_row]), 
                       df.iloc[row_idx:]]).reset_index(drop=True)
        
        print(f"Inserted date at row {row_idx + 2}")
    
    # Column AF is the 32nd column (0-indexed: 31)
    # Column AG is the 33rd column (0-indexed: 32)
    # AF = 31, AG = 32
    af_col = 31  # WTI
    ag_col = 32  # IBIT
    
    # Ensure the dataframe has enough columns
    while len(df.columns) <= ag_col:
        df[f'Unnamed_{len(df.columns)}'] = None
    
    # Update the values
    if prices['WTI'] is not None:
        df.iloc[row_idx, af_col] = prices['WTI']
        print(f"Updated WTI (column AF) with ${prices['WTI']:.2f}")
    
    if prices['IBIT'] is not None:
        df.iloc[row_idx, ag_col] = prices['IBIT']
        print(f"Updated IBIT (column AG) with ${prices['IBIT']:.2f}")
    
    # Save back to ODS file
    print(f"\nSaving changes to {file_path}...")
    df.to_excel(file_path, sheet_name='journal', engine='odf', index=False)
    print("Done!")


def main():
    """Main function to orchestrate the stock price update."""
    # Path to the ODS file
    file_path = Path(__file__).parent / "Dividends JRS macro.ods"
    
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        return
    
    # Fetch closing prices
    prices = get_closing_prices()
    
    # Check if we got any prices
    if all(p is None for p in prices.values()):
        print("\nError: Could not fetch any stock prices. Aborting.")
        return
    
    # Update the spreadsheet
    try:
        update_spreadsheet(file_path, prices)
    except Exception as e:
        print(f"\nError updating spreadsheet: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

