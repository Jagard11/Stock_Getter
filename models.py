"""
Database models for the Inspector bug tracking system.
"""
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path


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


def load_config() -> Dict[str, Any]:
    """Load the inspector configuration."""
    config_path = Path("Inspector/inspector_config.json")
    if config_path.exists():
        with open(config_path, 'r') as f:
            return json.load(f)
    return {}


def save_config(config: Dict[str, Any]):
    """Save the inspector configuration."""
    config_path = Path("Inspector/inspector_config.json")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)

