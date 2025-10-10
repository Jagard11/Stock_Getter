"""
Database models for the Inspector bug tracking system.
"""
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path

try:
    import yfinance as yf
except ImportError:
    yf = None


class Database:
    """Handles all database operations for the Inspector system."""
    
    def __init__(self, db_path: str = "inspector.db"):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Initialize the database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create tasks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                detected_in TEXT NOT NULL,
                fix_by_milestone TEXT NOT NULL,
                severity TEXT NOT NULL,
                priority TEXT NOT NULL,
                status TEXT NOT NULL,
                created TEXT NOT NULL,
                modified TEXT NOT NULL,
                summary TEXT NOT NULL,
                description TEXT NOT NULL,
                additional_info TEXT,
                database_id TEXT NOT NULL
            )
        """)
        
        # Create attachments table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                filepath TEXT NOT NULL,
                uploaded_at TEXT NOT NULL,
                FOREIGN KEY (task_id) REFERENCES tasks (id)
            )
        """)
        
        # Create portfolio dates table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_dates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL UNIQUE,
                imported_at TEXT NOT NULL
            )
        """)
        
        # Create portfolio holdings table (normalized for any symbols)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_holdings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                value REAL,
                column_order INTEGER,
                FOREIGN KEY (date_id) REFERENCES portfolio_dates (id),
                UNIQUE(date_id, symbol)
            )
        """)
        
        # Create settings table for user preferences
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                modified_at TEXT NOT NULL
            )
        """)
        
        # Create symbol_mappings table - Maps journal symbols to Yahoo Finance tickers
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS symbol_mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                journal_symbol TEXT NOT NULL UNIQUE,
                yahoo_symbol TEXT NOT NULL,
                created_at TEXT NOT NULL,
                modified_at TEXT NOT NULL
            )
        """)
        
        # Create auto_fetch_symbols table - Symbols to fetch during import even if not in CSV
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS auto_fetch_symbols (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL UNIQUE,
                enabled INTEGER DEFAULT 1,
                created_at TEXT NOT NULL
            )
        """)
        
        # Create calculated_columns table - Columns computed from CSV data
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS calculated_columns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                column_name TEXT NOT NULL UNIQUE,
                calculation_type TEXT NOT NULL,
                config_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                modified_at TEXT NOT NULL
            )
        """)
        
        # Create excluded_symbols table - Symbols to hide from journal
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS excluded_symbols (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL UNIQUE,
                reason TEXT,
                created_at TEXT NOT NULL
            )
        """)
        
        # Create import_warnings table - Track import validation warnings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS import_warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                import_date TEXT NOT NULL,
                warning_type TEXT NOT NULL,
                message TEXT NOT NULL,
                severity TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        
        # Create value_scaling_rules table - Scale values during import (divide by factor)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS value_scaling_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                column_name TEXT NOT NULL UNIQUE,
                digits_to_remove INTEGER NOT NULL DEFAULT 3,
                enabled INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                modified_at TEXT NOT NULL
            )
        """)
        
        # Migration: Check if value_scaling_rules table exists and has correct schema
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='value_scaling_rules'")
        if cursor.fetchone():
            # Check if digits_to_remove column exists
            cursor.execute("PRAGMA table_info(value_scaling_rules)")
            columns = [row[1] for row in cursor.fetchall()]
            if 'digits_to_remove' not in columns:
                # Old schema, need to recreate
                print("Migrating value_scaling_rules table...")
                cursor.execute("DROP TABLE IF EXISTS value_scaling_rules")
                cursor.execute("""
                    CREATE TABLE value_scaling_rules (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        column_name TEXT NOT NULL UNIQUE,
                        digits_to_remove INTEGER NOT NULL DEFAULT 3,
                        enabled INTEGER DEFAULT 1,
                        created_at TEXT NOT NULL,
                        modified_at TEXT NOT NULL
                    )
                """)
        
        # Create dividend_payments table - Track dividend payments for symbols
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dividend_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                payment_date TEXT NOT NULL,
                amount_paid REAL NOT NULL,
                shares_held REAL,
                dividend_per_share REAL,
                account_number TEXT,
                notes TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(symbol, payment_date)
            )
        """)
        
        # Create dividend_tracking table - Track initial costs and yield calculations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dividend_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL UNIQUE,
                initial_cost REAL NOT NULL,
                shares_purchased REAL,
                purchase_date TEXT,
                account_number TEXT,
                notes TEXT,
                created_at TEXT NOT NULL,
                modified_at TEXT NOT NULL
            )
        """)
        
        conn.commit()
        conn.close()
    
    def get_connection(self):
        """Get a database connection."""
        return sqlite3.connect(self.db_path)
    
    def create_task(self, task_data: Dict[str, Any]) -> str:
        """Create a new task."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO tasks 
            (id, type, detected_in, fix_by_milestone, severity, priority, status, 
             created, modified, summary, description, additional_info, database_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task_data['id'],
            task_data.get('type', 'task'),
            task_data.get('detected_in', '1.0.0'),
            task_data.get('fix_by_milestone', '1.0.0'),
            task_data.get('severity', 'Medium'),
            task_data.get('priority', 'Medium'),
            task_data.get('status', 'active'),
            task_data.get('created', datetime.now().isoformat()),
            task_data.get('modified', datetime.now().isoformat()),
            task_data['summary'],
            task_data['description'],
            task_data.get('additional_info', ''),
            task_data.get('database_id', 'default')
        ))
        
        conn.commit()
        conn.close()
        return task_data['id']
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a task by ID."""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def get_all_tasks(self, database_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all tasks, optionally filtered by database_id."""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if database_id:
            cursor.execute("SELECT * FROM tasks WHERE database_id = ? ORDER BY created DESC", (database_id,))
        else:
            cursor.execute("SELECT * FROM tasks ORDER BY created DESC")
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def update_task(self, task_id: str, updates: Dict[str, Any]) -> bool:
        """Update a task."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Add modified timestamp
        updates['modified'] = datetime.now().isoformat()
        
        # Build UPDATE query dynamically
        set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
        values = list(updates.values()) + [task_id]
        
        cursor.execute(f"UPDATE tasks SET {set_clause} WHERE id = ?", values)
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    def delete_task(self, task_id: str) -> bool:
        """Delete a task."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Delete attachments first
        cursor.execute("DELETE FROM attachments WHERE task_id = ?", (task_id,))
        # Delete task
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    def add_attachment(self, task_id: str, filename: str, filepath: str) -> int:
        """Add an attachment to a task."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO attachments (task_id, filename, filepath, uploaded_at)
            VALUES (?, ?, ?, ?)
        """, (task_id, filename, filepath, datetime.now().isoformat()))
        
        attachment_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return attachment_id
    
    def get_attachments(self, task_id: str) -> List[Dict[str, Any]]:
        """Get all attachments for a task."""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM attachments WHERE task_id = ?", (task_id,))
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def import_portfolio_csv(self, csv_data: List[Dict[str, Any]]) -> int:
        """Import portfolio data from CSV with any symbols."""
        conn = self.get_connection()
        cursor = conn.cursor()
        imported_count = 0
        
        # Get column order from first row (preserve CSV column order)
        if csv_data:
            first_row = csv_data[0]
            # Get columns in order, excluding 'Date'
            column_order = [col for col in first_row.keys() if col.lower() != 'date']
        else:
            column_order = []
        
        for row in csv_data:
            try:
                # Get date from row
                date = row.get('Date') or row.get('date')
                if not date:
                    continue
                
                # Convert Excel serial dates to readable format
                date = self._convert_excel_date(date)
                
                # Insert or get date record
                cursor.execute("""
                    INSERT OR IGNORE INTO portfolio_dates (date, imported_at)
                    VALUES (?, ?)
                """, (date, datetime.now().isoformat()))
                
                cursor.execute("SELECT id FROM portfolio_dates WHERE date = ?", (date,))
                date_id = cursor.fetchone()[0]
                
                # Delete existing holdings for this date (for replacement)
                cursor.execute("DELETE FROM portfolio_holdings WHERE date_id = ?", (date_id,))
                
                # Insert all columns except 'Date' as holdings, preserving order
                for order_idx, symbol in enumerate(column_order):
                    if symbol in row:
                        float_value = self._get_float_value(row, symbol)
                        if float_value is not None:
                            cursor.execute("""
                                INSERT INTO portfolio_holdings (date_id, symbol, value, column_order)
                                VALUES (?, ?, ?, ?)
                            """, (date_id, symbol, float_value, order_idx))
                
                imported_count += 1
            except Exception as e:
                print(f"Error importing row for date {date}: {e}")
                continue
        
        conn.commit()
        conn.close()
        return imported_count
    
    def _get_float_value(self, row: Dict[str, Any], key: str) -> Optional[float]:
        """Helper to safely convert a value to float."""
        value = row.get(key)
        if value is None or value == '':
            return None
        try:
            # Remove currency symbols and commas
            if isinstance(value, str):
                value = value.replace('$', '').replace(',', '').strip()
            return float(value)
        except (ValueError, TypeError):
            return None
    
    def _convert_excel_date(self, date_value: str) -> str:
        """Convert Excel serial date number to formatted date string.
        
        Args:
            date_value: Either an Excel serial number (e.g., "45931") or a date string
        
        Returns:
            Formatted date string in "DayName YYYY-MM-DD" format
        """
        # Try to detect if it's an Excel serial number (typically 5 digits for recent dates)
        try:
            # If it's a number-like string, try to convert from Excel serial
            cleaned_value = date_value.strip()
            if cleaned_value.replace('.', '').replace('-', '').isdigit():
                # Check if it looks like an Excel serial (positive integer, typically 40000-50000 for 2010-2040)
                serial = float(cleaned_value)
                if 40000 <= serial <= 60000:  # Reasonable range for Excel dates 2009-2064
                    # Excel epoch is December 30, 1899
                    excel_epoch = datetime(1899, 12, 30)
                    converted_date = excel_epoch + timedelta(days=serial)
                    # Format as "DayName YYYY-MM-DD"
                    return converted_date.strftime("%a %Y-%m-%d")
        except (ValueError, AttributeError):
            pass
        
        # If it's already in a good format or conversion failed, return as-is
        return date_value
    
    def get_portfolio_data(self) -> tuple[List[Dict[str, Any]], List[str]]:
        """Get all portfolio data ordered by date descending.
        
        Returns:
            Tuple of (data_rows, column_names) where data_rows is a list of dicts
            with 'date' and symbol keys, and column_names is the list of unique symbols
            in their original CSV column order.
        """
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all dates - sort by the YYYY-MM-DD portion (after day name and space)
        # Date format is "Wed 2025-10-01", so we extract from position 5 onwards for sorting
        cursor.execute("""
            SELECT id, date 
            FROM portfolio_dates 
            ORDER BY substr(date, instr(date, ' ') + 1) DESC
        """)
        dates = cursor.fetchall()
        
        # Get all unique symbols in their original column order
        cursor.execute("""
            SELECT DISTINCT symbol, MIN(column_order) as min_order
            FROM portfolio_holdings 
            WHERE column_order IS NOT NULL
            GROUP BY symbol
            ORDER BY min_order
        """)
        symbols_with_order = cursor.fetchall()
        
        # If we have column_order data, use it; otherwise fall back to alphabetical
        if symbols_with_order and symbols_with_order[0]['min_order'] is not None:
            symbols = [row['symbol'] for row in symbols_with_order]
        else:
            # Fallback for old data without column_order
            cursor.execute("SELECT DISTINCT symbol FROM portfolio_holdings ORDER BY symbol")
            symbols = [row[0] for row in cursor.fetchall()]
        
        # Build data structure
        data_rows = []
        for date_row in dates:
            date_id = date_row['id']
            date = date_row['date']
            
            # Get holdings for this date
            cursor.execute("""
                SELECT symbol, value 
                FROM portfolio_holdings 
                WHERE date_id = ?
            """, (date_id,))
            holdings = cursor.fetchall()
            
            # Build row dict
            row_data = {'date': date}
            for holding in holdings:
                row_data[holding['symbol']] = holding['value']
            
            # Fill in None for missing symbols
            for symbol in symbols:
                if symbol not in row_data:
                    row_data[symbol] = None
            
            data_rows.append(row_data)
        
        conn.close()
        return data_rows, symbols
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a setting value by key."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return row[0]
        return default
    
    def set_setting(self, key: str, value: str) -> bool:
        """Set a setting value."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO settings (key, value, modified_at)
            VALUES (?, ?, ?)
        """, (key, value, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        return True
    
    def get_all_settings(self) -> Dict[str, str]:
        """Get all settings as a dictionary."""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT key, value FROM settings")
        rows = cursor.fetchall()
        conn.close()
        
        return {row['key']: row['value'] for row in rows}
    
    def update_column_order(self, symbol_order: List[str]) -> bool:
        """Update the column order for all symbols.
        
        Args:
            symbol_order: List of symbols in the desired order
        
        Returns:
            True if successful
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Update column_order for each symbol
            for new_order, symbol in enumerate(symbol_order):
                cursor.execute("""
                    UPDATE portfolio_holdings
                    SET column_order = ?
                    WHERE symbol = ?
                """, (new_order, symbol))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error updating column order: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def fix_excel_serial_dates(self) -> int:
        """Convert existing Excel serial date numbers to readable format.
        
        Returns:
            Number of dates converted
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        converted_count = 0
        
        try:
            # Get all dates
            cursor.execute("SELECT id, date FROM portfolio_dates")
            dates = cursor.fetchall()
            
            for date_id, date_str in dates:
                # Try to convert if it's an Excel serial
                converted = self._convert_excel_date(date_str)
                
                # If conversion happened (result is different), update the database
                if converted != date_str:
                    cursor.execute("""
                        UPDATE portfolio_dates
                        SET date = ?
                        WHERE id = ?
                    """, (converted, date_id))
                    converted_count += 1
                    print(f"Converted: {date_str} -> {converted}")
            
            conn.commit()
            return converted_count
        except Exception as e:
            print(f"Error converting dates: {e}")
            conn.rollback()
            return 0
        finally:
            conn.close()
    
    def update_portfolio_value(self, date: str, symbol: str, value: Optional[float]) -> bool:
        """Update a single portfolio value for a specific date and symbol.
        
        Args:
            date: The date string (e.g., "Wed 2025-10-01")
            symbol: The stock symbol/column name
            value: The new value (or None to clear)
        
        Returns:
            True if successful
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Get the date_id for this date
            cursor.execute("SELECT id FROM portfolio_dates WHERE date = ?", (date,))
            row = cursor.fetchone()
            
            if not row:
                return False
            
            date_id = row[0]
            
            if value is None:
                # Delete the holding if value is None
                cursor.execute("""
                    DELETE FROM portfolio_holdings
                    WHERE date_id = ? AND symbol = ?
                """, (date_id, symbol))
            else:
                # Update or insert the value
                cursor.execute("""
                    INSERT INTO portfolio_holdings (date_id, symbol, value, column_order)
                    VALUES (?, ?, ?, (SELECT column_order FROM portfolio_holdings WHERE symbol = ? LIMIT 1))
                    ON CONFLICT(date_id, symbol) 
                    DO UPDATE SET value = ?
                """, (date_id, symbol, value, symbol, value))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error updating portfolio value: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def update_portfolio_date(self, old_date: str, new_date: str) -> bool:
        """Update a date in the portfolio.
        
        Args:
            old_date: The current date string
            new_date: The new date string
        
        Returns:
            True if successful
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Update the date
            cursor.execute("""
                UPDATE portfolio_dates
                SET date = ?
                WHERE date = ?
            """, (new_date, old_date))
            
            success = cursor.rowcount > 0
            conn.commit()
            return success
        except Exception as e:
            print(f"Error updating portfolio date: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def delete_portfolio_date(self, date: str) -> bool:
        """Delete a date and all its associated portfolio holdings.
        
        Args:
            date: The date string to delete
        
        Returns:
            True if successful
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Get the date_id
            cursor.execute("SELECT id FROM portfolio_dates WHERE date = ?", (date,))
            row = cursor.fetchone()
            
            if not row:
                return False
            
            date_id = row[0]
            
            # Delete all holdings for this date
            cursor.execute("""
                DELETE FROM portfolio_holdings
                WHERE date_id = ?
            """, (date_id,))
            
            # Delete the date itself
            cursor.execute("""
                DELETE FROM portfolio_dates
                WHERE id = ?
            """, (date_id,))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error deleting portfolio date: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def import_stock_holdings_csv(self, csv_data: List[List[str]]) -> Dict[str, Any]:
        """Import stock holdings from CSV with account-based structure.
        
        This method handles CSV files with the following structure:
        - Multiple sections separated by empty rows
        - First section contains holdings data with columns:
          Account Number, Investment Name, Symbol, Shares, Share Price, Total Value
        - Second instance of "Account Number" marks the end of holdings data
        - Multiple accounts may hold the same stock symbol
        
        Applies import rules:
        - Symbol mappings (for Yahoo Finance fetch)
        - Calculated columns (formulas from CSV data)
        - Auto-fetch symbols (fetch even if not in CSV)
        - Excluded symbols (hide from journal)
        
        Args:
            csv_data: List of rows, where each row is a list of cell values
        
        Returns:
            Dictionary with import results and warnings
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        warnings = []
        
        try:
            # === STEP 1: Parse CSV Data ===
            # Find the second instance of "Account Number" in column A (index 0)
            account_number_count = 0
            holdings_end_index = len(csv_data)
            
            for idx, row in enumerate(csv_data):
                if row and len(row) > 0 and row[0] and 'Account Number' in str(row[0]):
                    account_number_count += 1
                    if account_number_count == 2:
                        holdings_end_index = idx
                        break
            
            # Extract holdings from top section only
            # Find the first instance (header row)
            header_index = -1
            for idx, row in enumerate(csv_data[:holdings_end_index]):
                if row and len(row) > 0 and row[0] and 'Account Number' in str(row[0]):
                    header_index = idx
                    break
            
            if header_index == -1:
                return {'symbols_imported': 0, 'error': 'Could not find header row', 'warnings': []}
            
            # Parse ALL holdings data (keep account-level detail for calculated columns)
            raw_holdings = []  # List of {account, symbol, shares, share_price, total_value}
            symbols_from_csv = {}  # symbol -> share_price (for unique symbols)
            
            for row in csv_data[header_index + 1:holdings_end_index]:
                # Skip empty rows
                if not row or len(row) < 6:
                    continue
                
                # Skip if first column is empty or contains "Account Number"
                if not row[0] or 'Account Number' in str(row[0]):
                    continue
                
                # Extract data
                account_number = str(row[0]).strip()
                investment_name = str(row[1]).strip() if len(row) > 1 else ""
                symbol = str(row[2]).strip() if len(row) > 2 else ""
                shares_str = str(row[3]).strip() if len(row) > 3 else ""
                share_price_str = str(row[4]).strip() if len(row) > 4 else ""
                total_value_str = str(row[5]).strip() if len(row) > 5 else ""
                
                # Skip rows without valid symbol
                if not symbol or symbol.lower() == 'null':
                    continue
                
                # Parse values
                try:
                    shares = float(shares_str.replace(',', '')) if shares_str else 0
                    share_price = float(share_price_str.replace('$', '').replace(',', '')) if share_price_str else 0
                    total_value = float(total_value_str.replace('$', '').replace(',', '')) if total_value_str else 0
                except (ValueError, AttributeError):
                    continue
                
                # Store raw holding for calculated columns
                raw_holdings.append({
                    'account': account_number,
                    'investment_name': investment_name,
                    'symbol': symbol,
                    'shares': shares,
                    'share_price': share_price,
                    'total_value': total_value
                })
                
                # Store unique symbol price
                if symbol not in symbols_from_csv and share_price > 0:
                    symbols_from_csv[symbol] = share_price
            
            # === STEP 2: Get Import Rules ===
            calculated_columns = self.get_calculated_columns()
            auto_fetch_symbols = [s for s in self.get_auto_fetch_symbols() if s['enabled']]
            # Case-insensitive exclusion list
            excluded_symbols_list = [s['symbol'].upper() for s in self.get_excluded_symbols()]
            
            # === STEP 3: Get Date and Validate ===
            today = datetime.now()
            date_str = today.strftime("%a %Y-%m-%d")
            
            # Check for market hours warning
            if today.weekday() < 5 and 9 <= today.hour < 16:  # Weekday, market hours
                warnings.append({
                    'type': 'market_hours',
                    'severity': 'warning',
                    'message': 'Market is still open. Prices may not reflect today\'s close.'
                })
            
            # Check for weekend/holiday warning
            if today.weekday() >= 5:  # Saturday or Sunday
                warnings.append({
                    'type': 'non_trading_day',
                    'severity': 'info',
                    'message': f'{today.strftime("%A")} is not a trading day.'
                })
            
            # Check for missing days
            cursor.execute("""
                SELECT date FROM portfolio_dates
                ORDER BY substr(date, instr(date, ' ') + 1) DESC
                LIMIT 1
            """)
            last_date_row = cursor.fetchone()
            if last_date_row:
                last_date_str = last_date_row[0]
                if ' ' in last_date_str:
                    try:
                        last_date = datetime.strptime(last_date_str.split(' ', 1)[1], '%Y-%m-%d')
                        days_gap = (today - last_date).days
                        if days_gap > 1:
                            warnings.append({
                                'type': 'missing_days',
                                'severity': 'info',
                                'message': f'Gap of {days_gap} days since last import on {last_date_str}.'
                            })
                    except:
                        pass
            
            # === STEP 4: Calculate Formula Columns ===
            final_values = {}  # symbol -> value
            csv_symbols = []
            calculated_symbols = []
            auto_fetched_symbols = []
            excluded_symbols_used = []
            
            # Add CSV symbols (excluding those that will be excluded)
            for symbol, price in symbols_from_csv.items():
                # Case-insensitive exclusion check
                if symbol.upper() not in excluded_symbols_list:
                    final_values[symbol] = price
                    csv_symbols.append(symbol)
                else:
                    excluded_symbols_used.append(symbol)
            
            # Process calculated columns
            for calc_col in calculated_columns:
                col_name = calc_col['column_name']
                calc_type = calc_col['calculation_type']
                config = calc_col['config']
                
                if calc_type == 'account_filter':
                    # Filter holdings by account and optional symbol
                    account_filter = config.get('account_filter', '')
                    source_symbol = config.get('source_symbol', '')
                    value_column = config.get('value_column', 'total_value')
                    aggregation = config.get('aggregation', 'sum')
                    
                    # Filter holdings
                    filtered = [h for h in raw_holdings if h['account'] == account_filter]
                    if source_symbol:
                        filtered = [h for h in filtered if h['symbol'] == source_symbol]
                    
                    if not filtered:
                        warnings.append({
                            'type': 'calculated_column',
                            'severity': 'warning',
                            'message': f'{col_name}: No matching entries found (Account #{account_filter})'
                        })
                        continue
                    
                    # Get values
                    values = [h[value_column] for h in filtered]
                    
                    # Aggregate
                    if aggregation == 'sum':
                        result = sum(values)
                    elif aggregation == 'single':
                        result = values[0] if values else 0
                    else:
                        result = sum(values)  # Default to sum
                    
                    final_values[col_name] = result
                    calculated_symbols.append(col_name)
            
            # === STEP 5: Auto-Fetch Missing Symbols ===
            for auto_fetch in auto_fetch_symbols:
                fetch_symbol = auto_fetch['symbol']
                
                # Check if this is a Yahoo symbol that maps back to a journal symbol
                # e.g., CL=F should create WTI column if mapping exists: WTI → CL=F
                journal_symbol = self.get_reverse_symbol_mapping(fetch_symbol)
                if journal_symbol:
                    # This is a Yahoo symbol, use the journal name as column name
                    column_name = journal_symbol
                    yahoo_symbol_to_fetch = fetch_symbol
                    print(f"Auto-fetching {fetch_symbol} (will create {column_name} column)...")
                else:
                    # No reverse mapping, use the symbol as-is
                    column_name = fetch_symbol
                    yahoo_symbol_to_fetch = fetch_symbol
                    print(f"Auto-fetching {fetch_symbol}...")
                
                # Don't overwrite existing columns
                if column_name not in final_values:
                    fetch_result = fetch_yahoo_price(column_name, date_str, self)
                    if fetch_result:
                        final_values[column_name] = fetch_result['price']
                        auto_fetched_symbols.append(column_name)
                        print(f"  ✓ Fetched {column_name} → ${fetch_result['price']:.2f} (using {fetch_result['yahoo_symbol']})")
                    else:
                        warning_msg = f'Could not fetch price for {column_name}'
                        if journal_symbol:
                            warning_msg += f' (tried {yahoo_symbol_to_fetch})'
                        warnings.append({
                            'type': 'auto_fetch',
                            'severity': 'warning',
                            'message': warning_msg
                        })
                        print(f"  ✗ Failed to fetch {column_name} (tried {fetch_result.get('yahoo_symbol', fetch_symbol) if fetch_result else yahoo_symbol_to_fetch})")
                else:
                    print(f"  ⊘ Skipping {column_name} (already exists in CSV or calculated columns)")
            
            # === STEP 6: Apply Value Scaling Rules ===
            scaling_rules = {r['column_name'].upper(): r for r in self.get_value_scaling_rules() if r['enabled']}
            if scaling_rules:
                print(f"Applying value scaling rules to {len(scaling_rules)} columns...")
                for column_name in list(final_values.keys()):
                    if column_name.upper() in scaling_rules:
                        rule = scaling_rules[column_name.upper()]
                        original_value = final_values[column_name]
                        divisor = 10 ** rule['digits_to_remove']
                        scaled_value = original_value / divisor
                        final_values[column_name] = scaled_value
                        print(f"  ⚖ Scaled {column_name}: ${original_value:,.0f} → ${scaled_value:,.0f} (÷{divisor})")
            
            # === STEP 7: Store to Database ===
            # Insert or get date record
            cursor.execute("""
                INSERT OR IGNORE INTO portfolio_dates (date, imported_at)
                VALUES (?, ?)
            """, (date_str, datetime.now().isoformat()))
            
            cursor.execute("SELECT id FROM portfolio_dates WHERE date = ?", (date_str,))
            date_id = cursor.fetchone()[0]
            
            # Get existing symbols to preserve column order
            cursor.execute("""
                SELECT DISTINCT symbol, MIN(column_order) as min_order
                FROM portfolio_holdings 
                WHERE column_order IS NOT NULL
                GROUP BY symbol
                ORDER BY min_order
            """)
            existing_symbols = [row[0] for row in cursor.fetchall()]
            
            # Determine column order for new symbols
            next_order = len(existing_symbols)
            
            # Insert/update holdings
            for symbol, value in final_values.items():
                # Determine column order
                if symbol in existing_symbols:
                    column_order = existing_symbols.index(symbol)
                else:
                    column_order = next_order
                    next_order += 1
                
                # Insert or update the holding
                cursor.execute("""
                    INSERT INTO portfolio_holdings (date_id, symbol, value, column_order)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(date_id, symbol) 
                    DO UPDATE SET value = ?, column_order = ?
                """, (date_id, symbol, value, column_order, value, column_order))
            
            # === STEP 8: Store Warnings ===
            now = datetime.now().isoformat()
            for warning in warnings:
                cursor.execute("""
                    INSERT INTO import_warnings (import_date, warning_type, message, severity, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (date_str, warning['type'], warning['message'], warning['severity'], now))
            
            conn.commit()
            
            return {
                'success': True,
                'date': date_str,
                'symbols_imported': len(final_values),
                'csv_symbols': csv_symbols,
                'calculated_symbols': calculated_symbols,
                'auto_fetched_symbols': auto_fetched_symbols,
                'excluded_symbols': excluded_symbols_used,
                'warnings': warnings
            }
            
        except Exception as e:
            print(f"Error importing stock holdings CSV: {e}")
            import traceback
            traceback.print_exc()
            conn.rollback()
            return {'success': False, 'error': str(e), 'warnings': warnings}
        finally:
            conn.close()
    
    def get_chart_data(self) -> Dict[str, Any]:
        """Get portfolio data formatted for charting.
        
        Returns:
            Dictionary with symbol -> list of {date, value} pairs
        """
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            # Get all dates sorted ascending (oldest first for charts)
            cursor.execute("""
                SELECT id, date 
                FROM portfolio_dates 
                ORDER BY substr(date, instr(date, ' ') + 1) ASC
            """)
            dates = cursor.fetchall()
            
            # Get all symbols
            cursor.execute("""
                SELECT DISTINCT symbol, MIN(column_order) as min_order
                FROM portfolio_holdings 
                WHERE column_order IS NOT NULL
                GROUP BY symbol
                ORDER BY min_order
            """)
            symbols = [row['symbol'] for row in cursor.fetchall()]
            
            # Build chart data for each symbol
            chart_data = {}
            for symbol in symbols:
                # Skip cash and e-trade symbols
                if symbol.lower() in ['cash', 'e-trade', 'etrade']:
                    continue
                
                data_points = []
                for date_row in dates:
                    date_id = date_row['id']
                    date_str = date_row['date']
                    
                    # Extract just the YYYY-MM-DD portion
                    if ' ' in date_str:
                        date_only = date_str.split(' ', 1)[1]
                    else:
                        date_only = date_str
                    
                    # Get value for this symbol and date
                    cursor.execute("""
                        SELECT value 
                        FROM portfolio_holdings 
                        WHERE date_id = ? AND symbol = ?
                    """, (date_id, symbol))
                    
                    row = cursor.fetchone()
                    if row and row['value'] is not None:
                        data_points.append({
                            'date': date_only,
                            'value': float(row['value'])
                        })
                
                # Only include symbols that have at least one data point
                if data_points:
                    chart_data[symbol] = data_points
            
            return chart_data
            
        finally:
            conn.close()
    
    def add_new_symbol(self, symbol: str) -> bool:
        """Add a new symbol to the portfolio.
        
        Args:
            symbol: The stock symbol to add
        
        Returns:
            True if successful
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Get the highest column_order value
            cursor.execute("""
                SELECT MAX(column_order) as max_order
                FROM portfolio_holdings
            """)
            row = cursor.fetchone()
            next_order = (row[0] + 1) if row[0] is not None else 0
            
            # Get all existing dates
            cursor.execute("SELECT id FROM portfolio_dates")
            date_ids = [row[0] for row in cursor.fetchall()]
            
            # Add the symbol with NULL value for all existing dates
            # This ensures it shows up in the table but with no values
            for date_id in date_ids:
                cursor.execute("""
                    INSERT INTO portfolio_holdings (date_id, symbol, value, column_order)
                    VALUES (?, ?, NULL, ?)
                """, (date_id, symbol, next_order))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error adding new symbol: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def remove_symbol(self, symbol: str) -> bool:
        """Remove a symbol from the portfolio.
        
        Args:
            symbol: The stock symbol to remove
        
        Returns:
            True if successful
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Delete all holdings for this symbol
            cursor.execute("""
                DELETE FROM portfolio_holdings
                WHERE symbol = ?
            """, (symbol,))
            
            rows_deleted = cursor.rowcount
            conn.commit()
            return rows_deleted > 0
        except Exception as e:
            print(f"Error removing symbol: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def get_all_time_high_stats(self) -> Dict[str, Any]:
        """Get all-time high statistics for the Total column.
        
        Returns:
            Dictionary with max, current, difference, and percent_diff
        """
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            # Check if 'Total' symbol exists
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM portfolio_holdings
                WHERE symbol = 'Total'
            """)
            if cursor.fetchone()['count'] == 0:
                return {
                    'max': 0,
                    'current': 0,
                    'difference': 0,
                    'percent_diff': 0,
                    'error': 'Total column not found'
                }
            
            # Get maximum value from Total column
            cursor.execute("""
                SELECT MAX(value) as max_value
                FROM portfolio_holdings
                WHERE symbol = 'Total' AND value IS NOT NULL
            """)
            max_row = cursor.fetchone()
            max_value = max_row['max_value'] if max_row and max_row['max_value'] else 0
            
            # Get most recent date
            cursor.execute("""
                SELECT id, date
                FROM portfolio_dates
                ORDER BY substr(date, instr(date, ' ') + 1) DESC
                LIMIT 1
            """)
            latest_date_row = cursor.fetchone()
            
            if not latest_date_row:
                return {
                    'max': max_value,
                    'current': 0,
                    'difference': 0,
                    'percent_diff': 0,
                    'error': 'No dates found'
                }
            
            latest_date_id = latest_date_row['id']
            
            # Get current value (most recent Total value)
            cursor.execute("""
                SELECT value
                FROM portfolio_holdings
                WHERE date_id = ? AND symbol = 'Total'
            """, (latest_date_id,))
            current_row = cursor.fetchone()
            current_value = current_row['value'] if current_row and current_row['value'] else 0
            
            # Calculate difference and percent difference
            difference = current_value - max_value
            percent_diff = 0
            if max_value > 0:
                percent_diff = (1 - (max_value - current_value) / max_value) * 100
            
            return {
                'max': float(max_value),
                'current': float(current_value),
                'difference': float(difference),
                'percent_diff': float(percent_diff)
            }
            
        finally:
            conn.close()
    
    # ========== Symbol Mappings Methods ==========
    
    def get_symbol_mappings(self) -> List[Dict[str, Any]]:
        """Get all symbol mappings."""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM symbol_mappings
            ORDER BY journal_symbol
        """)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def add_symbol_mapping(self, journal_symbol: str, yahoo_symbol: str) -> int:
        """Add a new symbol mapping."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO symbol_mappings (journal_symbol, yahoo_symbol, created_at, modified_at)
            VALUES (?, ?, ?, ?)
        """, (journal_symbol, yahoo_symbol, now, now))
        
        mapping_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return mapping_id
    
    def update_symbol_mapping(self, mapping_id: int, journal_symbol: str, yahoo_symbol: str) -> bool:
        """Update an existing symbol mapping."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        cursor.execute("""
            UPDATE symbol_mappings
            SET journal_symbol = ?, yahoo_symbol = ?, modified_at = ?
            WHERE id = ?
        """, (journal_symbol, yahoo_symbol, now, mapping_id))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    def delete_symbol_mapping(self, mapping_id: int) -> bool:
        """Delete a symbol mapping."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM symbol_mappings WHERE id = ?", (mapping_id,))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    def get_symbol_mapping(self, journal_symbol: str) -> Optional[str]:
        """Get Yahoo symbol for a journal symbol, or None if no mapping.
        
        Uses case-insensitive comparison for robustness.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT yahoo_symbol FROM symbol_mappings
            WHERE LOWER(journal_symbol) = LOWER(?)
        """, (journal_symbol,))
        
        row = cursor.fetchone()
        conn.close()
        
        return row[0] if row else None
    
    def get_reverse_symbol_mapping(self, yahoo_symbol: str) -> Optional[str]:
        """Get journal symbol for a Yahoo symbol (reverse lookup), or None if no mapping.
        
        Uses case-insensitive comparison for robustness.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT journal_symbol FROM symbol_mappings
            WHERE LOWER(yahoo_symbol) = LOWER(?)
        """, (yahoo_symbol,))
        
        row = cursor.fetchone()
        conn.close()
        
        return row[0] if row else None
    
    # ========== Auto-Fetch Symbols Methods ==========
    
    def get_auto_fetch_symbols(self) -> List[Dict[str, Any]]:
        """Get all auto-fetch symbols."""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM auto_fetch_symbols
            ORDER BY symbol
        """)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def add_auto_fetch_symbol(self, symbol: str) -> int:
        """Add a symbol to auto-fetch list."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO auto_fetch_symbols (symbol, enabled, created_at)
            VALUES (?, 1, ?)
        """, (symbol, now))
        
        symbol_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return symbol_id
    
    def toggle_auto_fetch_symbol(self, symbol_id: int, enabled: bool) -> bool:
        """Enable or disable an auto-fetch symbol."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE auto_fetch_symbols
            SET enabled = ?
            WHERE id = ?
        """, (1 if enabled else 0, symbol_id))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    def delete_auto_fetch_symbol(self, symbol_id: int) -> bool:
        """Delete an auto-fetch symbol."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM auto_fetch_symbols WHERE id = ?", (symbol_id,))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    # ========== Calculated Columns Methods ==========
    
    def get_calculated_columns(self) -> List[Dict[str, Any]]:
        """Get all calculated columns."""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM calculated_columns
            ORDER BY column_name
        """)
        rows = cursor.fetchall()
        conn.close()
        
        result = []
        for row in rows:
            data = dict(row)
            data['config'] = json.loads(data['config_json'])
            result.append(data)
        
        return result
    
    def add_calculated_column(self, column_name: str, calculation_type: str, config: Dict[str, Any]) -> int:
        """Add a new calculated column."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO calculated_columns (column_name, calculation_type, config_json, created_at, modified_at)
            VALUES (?, ?, ?, ?, ?)
        """, (column_name, calculation_type, json.dumps(config), now, now))
        
        column_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return column_id
    
    def update_calculated_column(self, column_id: int, column_name: str, calculation_type: str, config: Dict[str, Any]) -> bool:
        """Update an existing calculated column."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        cursor.execute("""
            UPDATE calculated_columns
            SET column_name = ?, calculation_type = ?, config_json = ?, modified_at = ?
            WHERE id = ?
        """, (column_name, calculation_type, json.dumps(config), now, column_id))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    def delete_calculated_column(self, column_id: int) -> bool:
        """Delete a calculated column."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM calculated_columns WHERE id = ?", (column_id,))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    # ========== Excluded Symbols Methods ==========
    
    def get_excluded_symbols(self) -> List[Dict[str, Any]]:
        """Get all excluded symbols."""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM excluded_symbols
            ORDER BY symbol
        """)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def add_excluded_symbol(self, symbol: str, reason: str = "") -> int:
        """Add a symbol to the exclusion list."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO excluded_symbols (symbol, reason, created_at)
            VALUES (?, ?, ?)
        """, (symbol, reason, now))
        
        exclusion_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return exclusion_id
    
    def delete_excluded_symbol(self, exclusion_id: int) -> bool:
        """Delete an excluded symbol."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM excluded_symbols WHERE id = ?", (exclusion_id,))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    def is_symbol_excluded(self, symbol: str) -> bool:
        """Check if a symbol is excluded."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) FROM excluded_symbols
            WHERE symbol = ?
        """, (symbol,))
        
        count = cursor.fetchone()[0]
        conn.close()
        
        return count > 0
    
    # ========== Value Scaling Rules Methods ==========
    
    def get_value_scaling_rules(self) -> List[Dict[str, Any]]:
        """Get all value scaling rules."""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM value_scaling_rules
            ORDER BY column_name
        """)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def add_value_scaling_rule(self, column_name: str, digits_to_remove: int = 3) -> int:
        """Add a value scaling rule."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO value_scaling_rules (column_name, digits_to_remove, enabled, created_at, modified_at)
            VALUES (?, ?, 1, ?, ?)
        """, (column_name, digits_to_remove, now, now))
        
        rule_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return rule_id
    
    def update_value_scaling_rule(self, rule_id: int, column_name: str, digits_to_remove: int) -> bool:
        """Update a value scaling rule."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        cursor.execute("""
            UPDATE value_scaling_rules
            SET column_name = ?, digits_to_remove = ?, modified_at = ?
            WHERE id = ?
        """, (column_name, digits_to_remove, now, rule_id))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    def toggle_value_scaling_rule(self, rule_id: int, enabled: bool) -> bool:
        """Enable or disable a value scaling rule."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE value_scaling_rules
            SET enabled = ?
            WHERE id = ?
        """, (1 if enabled else 0, rule_id))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    def delete_value_scaling_rule(self, rule_id: int) -> bool:
        """Delete a value scaling rule."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM value_scaling_rules WHERE id = ?", (rule_id,))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    # ========== Import Warnings Methods ==========
    
    def add_import_warning(self, import_date: str, warning_type: str, message: str, severity: str) -> int:
        """Add an import warning."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO import_warnings (import_date, warning_type, message, severity, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (import_date, warning_type, message, severity, now))
        
        warning_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return warning_id
    
    def get_import_warnings(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent import warnings."""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM import_warnings
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    # ========== Dividend Tracking Methods ==========
    
    def get_dividend_tracking_symbols(self) -> List[Dict[str, Any]]:
        """Get all symbols being tracked for dividend yield calculations."""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM dividend_tracking
            ORDER BY symbol
        """)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def add_dividend_tracking(
        self,
        symbol: str,
        initial_cost: float,
        shares_purchased: Optional[float] = None,
        purchase_date: Optional[str] = None,
        account_number: Optional[str] = None,
        notes: Optional[str] = None
    ) -> int:
        """Add a new symbol to dividend tracking."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO dividend_tracking 
            (symbol, initial_cost, shares_purchased, purchase_date, account_number, notes, created_at, modified_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (symbol, initial_cost, shares_purchased, purchase_date, account_number, notes, now, now))
        
        tracking_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return tracking_id
    
    def update_dividend_tracking(
        self,
        tracking_id: int,
        initial_cost: float,
        shares_purchased: Optional[float] = None,
        purchase_date: Optional[str] = None,
        account_number: Optional[str] = None,
        notes: Optional[str] = None
    ) -> bool:
        """Update an existing dividend tracking entry."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        cursor.execute("""
            UPDATE dividend_tracking
            SET initial_cost = ?, shares_purchased = ?, purchase_date = ?, 
                account_number = ?, notes = ?, modified_at = ?
            WHERE id = ?
        """, (initial_cost, shares_purchased, purchase_date, account_number, notes, now, tracking_id))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    def delete_dividend_tracking(self, tracking_id: int) -> bool:
        """Delete a dividend tracking entry."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM dividend_tracking WHERE id = ?", (tracking_id,))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    def get_dividend_payments(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all dividend payments, optionally filtered by symbol."""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if symbol:
            cursor.execute("""
                SELECT * FROM dividend_payments
                WHERE symbol = ?
                ORDER BY payment_date DESC
            """, (symbol,))
        else:
            cursor.execute("""
                SELECT * FROM dividend_payments
                ORDER BY symbol, payment_date DESC
            """)
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def add_dividend_payment(
        self,
        symbol: str,
        payment_date: str,
        amount_paid: float,
        shares_held: Optional[float] = None,
        dividend_per_share: Optional[float] = None,
        account_number: Optional[str] = None,
        notes: Optional[str] = None
    ) -> int:
        """Add a new dividend payment record."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO dividend_payments 
            (symbol, payment_date, amount_paid, shares_held, dividend_per_share, 
             account_number, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (symbol, payment_date, amount_paid, shares_held, dividend_per_share, 
              account_number, notes, now))
        
        payment_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return payment_id
    
    def update_dividend_payment(
        self,
        payment_id: int,
        payment_date: str,
        amount_paid: float,
        shares_held: Optional[float] = None,
        dividend_per_share: Optional[float] = None,
        account_number: Optional[str] = None,
        notes: Optional[str] = None
    ) -> bool:
        """Update an existing dividend payment."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE dividend_payments
            SET payment_date = ?, amount_paid = ?, shares_held = ?, 
                dividend_per_share = ?, account_number = ?, notes = ?
            WHERE id = ?
        """, (payment_date, amount_paid, shares_held, dividend_per_share, 
              account_number, notes, payment_id))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    def delete_dividend_payment(self, payment_id: int) -> bool:
        """Delete a dividend payment."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM dividend_payments WHERE id = ?", (payment_id,))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    def get_dividend_summary(self) -> List[Dict[str, Any]]:
        """Get dividend summary data for all tracked symbols.
        
        Calculates total payments and yield based on initial investment.
        """
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                dt.symbol,
                dt.initial_cost,
                dt.shares_purchased,
                dt.purchase_date,
                dt.account_number,
                COALESCE(SUM(dp.amount_paid), 0) as total_payments,
                COUNT(dp.id) as payment_count,
                CASE 
                    WHEN dt.initial_cost > 0 
                    THEN (COALESCE(SUM(dp.amount_paid), 0) / dt.initial_cost) * 100
                    ELSE 0
                END as yield_percentage
            FROM dividend_tracking dt
            LEFT JOIN dividend_payments dp ON dt.symbol = dp.symbol
            GROUP BY dt.symbol, dt.initial_cost, dt.shares_purchased, 
                     dt.purchase_date, dt.account_number
            ORDER BY dt.symbol
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def export_journal_to_csv(self) -> str:
        """Export portfolio journal data to CSV format.
        
        Returns CSV string with Date column followed by all symbol columns,
        maintaining the same format as the import to enable backup restoration.
        
        Returns:
            CSV formatted string
        """
        import io
        import csv
        
        # Get portfolio data
        data_rows, symbols = self.get_portfolio_data()
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header row
        header = ['Date'] + symbols
        writer.writerow(header)
        
        # Write data rows
        for row in data_rows:
            csv_row = [row['date']]
            for symbol in symbols:
                value = row.get(symbol)
                # Write empty string for None values, otherwise write the value
                csv_row.append('' if value is None else value)
            writer.writerow(csv_row)
        
        # Get CSV content
        csv_content = output.getvalue()
        output.close()
        
        return csv_content


def fetch_yahoo_price(symbol: str, date_str: str, db_instance: 'Database') -> Optional[Dict[str, Any]]:
    """Fetch stock price from Yahoo Finance for a given symbol and date.
    
    Args:
        symbol: The symbol to fetch (journal symbol, will be mapped if needed)
        date_str: Date in YYYY-MM-DD format or "DayName YYYY-MM-DD" format
        db_instance: Database instance for looking up symbol mappings
    
    Returns:
        Dictionary with 'price', 'yahoo_symbol', 'date' on success, None on failure
    """
    if yf is None:
        print(f"  ERROR: yfinance not installed")
        return None
    
    try:
        # Check for symbol mapping in database
        yahoo_symbol = db_instance.get_symbol_mapping(symbol)
        if not yahoo_symbol:
            yahoo_symbol = symbol  # No mapping, use symbol as-is
        
        # Parse the date - handle "DayName YYYY-MM-DD" format
        if ' ' in date_str:
            # Extract just the YYYY-MM-DD portion
            date_str = date_str.split(' ', 1)[1]
        
        # Fetch data from Yahoo Finance
        ticker = yf.Ticker(yahoo_symbol)
        
        # Get historical data for the specific date
        # Fetch a small range around the date to handle weekends/holidays (max 4 days back)
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        start_date = (date_obj - timedelta(days=4)).strftime('%Y-%m-%d')
        end_date = (date_obj + timedelta(days=1)).strftime('%Y-%m-%d')
        
        hist = ticker.history(start=start_date, end=end_date)
        
        if hist.empty:
            print(f"  ✗ No data from Yahoo Finance for {yahoo_symbol}")
            return None
        
        # Try to get the exact date, or the closest previous date
        if date_str in hist.index.strftime('%Y-%m-%d').tolist():
            price_data = hist[hist.index.strftime('%Y-%m-%d') == date_str].iloc[0]
            actual_date = date_str
        else:
            # Get the most recent price before or on the date
            price_data = hist.iloc[-1]
            actual_date = hist.index[-1].strftime('%Y-%m-%d')
            if actual_date != date_str:
                print(f"  ℹ️ Used {actual_date} (closest to {date_str})")
        
        price = float(price_data['Close'])
        
        return {
            'price': price,
            'yahoo_symbol': yahoo_symbol,
            'date': date_str
        }
        
    except Exception as e:
        print(f"  ERROR fetching price for {symbol}: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return None


def load_config() -> Dict[str, Any]:
    """Load the inspector configuration."""
    config_path = Path("Inspector/inspector_config.json")
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_config(config: Dict[str, Any]):
    """Save the inspector configuration."""
    config_path = Path("Inspector/inspector_config.json")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)

