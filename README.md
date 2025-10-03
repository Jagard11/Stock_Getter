# Stock Tracker

A comprehensive portfolio management and stock tracking application built with FastAPI and modern web technologies.

## Features

### 📊 Portfolio Journal
Track your portfolio holdings across multiple stocks and assets. View historical data and identify top performers at a glance. The journal provides:
- Date-based portfolio snapshots
- Multi-asset tracking
- Visual highlighting of maximum values
- Editable cells for manual data entry
- CSV import functionality

### 📈 Performance Analytics
Analyze your portfolio performance over time with detailed charts and metrics:
- Daily performance charts for each tracked symbol
- Interactive line charts with Chart.js
- Historical trend analysis
- Visual comparison across assets

### ⚙️ Settings & Data Management
- Import portfolio data from CSV files
- Import holdings from account-based CSV exports
- Theme customization with multiple accessibility options
- Column reordering for personalized views

## Getting Started

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd Stock_Getter
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the server:
   ```bash
   # On Linux/Mac
   ./start_server.sh
   
   # On Windows
   start_server.bat
   ```

4. Open your browser to `http://localhost:8000`

### Data Import

The application supports two types of CSV imports:

1. **Portfolio Journal CSV**: Date-based portfolio values
   - Format: Date column followed by symbol columns
   - Values represent portfolio positions or values

2. **Holdings CSV**: Account-based holdings export
   - Automatically fetches current prices from Yahoo Finance
   - Calculates position values based on holdings

## Technology Stack

- **Backend**: FastAPI (Python)
- **Database**: SQLite with Peewee ORM
- **Frontend**: Jinja2 templates, Chart.js
- **Data**: Yahoo Finance API (yfinance)
- **Styling**: Custom CSS with theme support

## Accessibility

Multiple theme options are available to suit different accessibility needs:
- Default (Dark)
- High Visibility
- Ultra High Contrast
- Light
- Light High Contrast

All UI elements are consistently formatted to work with the accessibility themes, including buttons, fonts, and background colors.

## License

This project is open source and available under the MIT License.

