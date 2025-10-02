# Stock Price Updater

This script automatically fetches today's closing prices for WTI and IBIT stocks and updates them in the "Dividends JRS macro.ods" spreadsheet.

## Installation

Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Usage

Run the script:

```bash
python update_stocks.py
```

The script will:
1. Fetch the latest closing prices for WTI (Crude Oil) and IBIT (BlackRock Bitcoin ETF)
2. Open the "Dividends JRS macro.ods" file
3. Find today's date in column A of the "journal" tab
4. If the date doesn't exist, insert it as a new row
5. Update columns AF (WTI) and AG (IBIT) with the fetched prices

## Stock Tickers

- **WTI**: CL=F (WTI Crude Oil Futures)
- **IBIT**: IBIT (iShares Bitcoin Trust)

## Notes

- The script uses `yfinance` to fetch stock data, which pulls from Yahoo Finance
- Prices are rounded to 2 decimal places
- If a date is inserted, it will be placed after the last existing date in the spreadsheet
- The script will show progress messages and any errors encountered

