# Stock Price Fetcher

This script fetches today's closing prices for WTI and IBIT stocks and displays them for easy copy/paste into your spreadsheet.

**Note:** This script does NOT automatically update your ODS file to avoid data corruption. Instead, it fetches the prices and copies them to your clipboard for manual entry.

## Configuration

The script automatically looks for `Dividends JRS macro.ods` in the script directory. If not found, it will:
1. Check the path specified in `config.json`
2. Prompt you to enter the file path
3. Save your path to `config.json` for future use

### Config File

The script uses `config.json` to specify:
- Path to the ODS file (defaults to script directory)
- Sheet name to update
- Column locations for date, WTI, and IBIT
- Stock tickers to fetch

**Example config.json:**
```json
{
  "ods_file_path": "/path/to/your/Dividends JRS macro.ods",
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
```

**Options:**
- Place `Dividends JRS macro.ods` in the script directory (easiest)
- Edit `config.json` to point to your ODS file location
- Let the script prompt you for the path on first run
- Create `config.local.json` for local overrides (ignored by git)

## Installation

A virtual environment has been set up with all dependencies. If you need to reinstall:

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

## Usage

Simply run the launcher script:

```bash
./launcher.sh
```

Or run the script manually with the virtual environment:

```bash
source venv/bin/activate
python update_stocks.py
deactivate
```

The script will:
1. Fetch the latest closing prices for WTI (Crude Oil) and IBIT (BlackRock Bitcoin ETF)
2. Display the prices in a clean, easy-to-read format
3. Copy the values to your clipboard (tab-separated) for easy pasting
4. Show you exactly where to paste them in your spreadsheet

**Why manual entry?**
After extensive testing, programmatic ODS file modification risks corrupting formulas and formatting. Manual copy/paste using "Paste Special > Values" is the safest approach.

## Stock Tickers

- **WTI**: CL=F (WTI Crude Oil Futures)
- **IBIT**: IBIT (iShares Bitcoin Trust)

## Notes

- The script uses `yfinance` to fetch stock data, which pulls from Yahoo Finance
- Prices are rounded to 2 decimal places
- If a date is inserted, it will be placed after the last existing date in the spreadsheet
- The script will show progress messages and any errors encountered

