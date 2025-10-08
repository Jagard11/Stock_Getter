"""
FastAPI server for the Stock Tracker application.
"""
import os
import csv
import io
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import yfinance as yf
import asyncio

from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from models import Database, load_config, save_config, fetch_yahoo_price


app = FastAPI(title="Inspector - Bug Tracking System")

# Setup templates and static files
templates = Jinja2Templates(directory="templates")
os.makedirs("static", exist_ok=True)
os.makedirs("uploads", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Initialize database
db = Database()

# Simple in-memory progress log for retroactive fetch operations
# Note: Single-user/simple scenario; replace with per-user/session storage if needed
fetch_progress_state = {
    "log": [],
    "in_progress": False,
    "result": None,
    "processed": 0,
    "total": 0
}


@app.get("/journal/add-retroactive-date/progress")
async def retroactive_progress():
    """Return current progress log for the retroactive fetch operation."""
    payload = {
        "in_progress": fetch_progress_state["in_progress"],
        "log": fetch_progress_state["log"][-200:],
        "processed": fetch_progress_state.get("processed", 0),
        "total": fetch_progress_state.get("total", 0)
    }
    if fetch_progress_state.get("result"):
        payload.update(fetch_progress_state["result"])  # includes summary fields
        payload["done"] = True
    else:
        payload["done"] = not fetch_progress_state["in_progress"]
    return JSONResponse(payload, headers={
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0"
    })


@app.get("/journal/add-retroactive-date/stream")
async def retroactive_progress_stream():
    """Server-Sent Events stream of progress lines for the retroactive fetch."""
    async def event_generator():
        last_index = 0
        yield "event: hello\ndata: {}\n\n"
        while fetch_progress_state["in_progress"] or last_index < len(fetch_progress_state["log"]):
            if len(fetch_progress_state["log"]) > last_index:
                new_lines = fetch_progress_state["log"][last_index:]
                last_index = len(fetch_progress_state["log"])
                for line in new_lines:
                    payload = json.dumps({
                        "line": line,
                        "processed": fetch_progress_state.get("processed", 0),
                        "total": fetch_progress_state.get("total", 0)
                    })
                    yield f"data: {payload}\n\n"
            await asyncio.sleep(0.4)
        summary = fetch_progress_state.get("result") or {}
        yield f"event: done\ndata: {json.dumps(summary)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0"
    })


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page for Stock Tracker."""
    config = load_config()
    current_theme = db.get_setting('theme', 'default')
    
    # Get portfolio statistics
    portfolio_rows, symbols = db.get_portfolio_data()
    
    stats = {
        "total_value": 0,
        "holdings_count": len(symbols),
        "days_recorded": len(portfolio_rows),
        "recent_performance": 0
    }
    
    # Calculate total portfolio value and performance
    if portfolio_rows:
        # Get most recent row
        latest_row = portfolio_rows[0]
        
        # Calculate total value
        total_value = 0
        for symbol in symbols:
            value = latest_row.get(symbol)
            if value is not None:
                total_value += value
        stats["total_value"] = total_value
        
        # Calculate performance if we have at least 2 data points
        if len(portfolio_rows) >= 2:
            previous_row = portfolio_rows[1]
            previous_total = 0
            for symbol in symbols:
                value = previous_row.get(symbol)
                if value is not None:
                    previous_total += value
            
            if previous_total > 0:
                performance = ((total_value - previous_total) / previous_total) * 100
                stats["recent_performance"] = performance
    
    # Get all-time high statistics
    ath_stats = db.get_all_time_high_stats()
    
    # Read README content
    readme_content = ""
    readme_path = Path("README.md")
    if readme_path.exists():
        readme_content = readme_path.read_text(encoding='utf-8')
    
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "config": config,
            "stats": stats,
            "ath_stats": ath_stats,
            "readme_content": readme_content,
            "current_theme": current_theme
        }
    )


@app.get("/db/{database_id}", response_class=HTMLResponse)
async def database_view(request: Request, database_id: str):
    """View all tasks for a specific database."""
    config = load_config()
    current_theme = db.get_setting('theme', 'default')
    tasks = db.get_all_tasks(database_id=database_id)
    
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "config": config,
            "tasks": tasks,
            "database_id": database_id,
            "current_theme": current_theme
        }
    )


@app.get("/db/{database_id}/bug/{bug_id}", response_class=HTMLResponse)
async def bug_detail(request: Request, database_id: str, bug_id: str):
    """View details of a specific bug/task."""
    config = load_config()
    current_theme = db.get_setting('theme', 'default')
    task = db.get_task(bug_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    attachments = db.get_attachments(bug_id)
    
    return templates.TemplateResponse(
        "task_detail.html",
        {
            "request": request,
            "config": config,
            "task": task,
            "attachments": attachments,
            "database_id": database_id,
            "current_theme": current_theme
        }
    )


@app.get("/db/{database_id}/bug/{bug_id}/edit", response_class=HTMLResponse)
async def bug_edit(request: Request, database_id: str, bug_id: str):
    """Edit form for a bug/task."""
    config = load_config()
    current_theme = db.get_setting('theme', 'default')
    task = db.get_task(bug_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return templates.TemplateResponse(
        "task_edit.html",
        {
            "request": request,
            "config": config,
            "task": task,
            "database_id": database_id,
            "current_theme": current_theme
        }
    )


@app.post("/db/{database_id}/bug/{bug_id}/edit")
async def bug_edit_submit(
    database_id: str,
    bug_id: str,
    summary: str = Form(...),
    description: str = Form(...),
    type: str = Form(...),
    status: str = Form(...),
    severity: str = Form(...),
    priority: str = Form(...),
    additional_info: Optional[str] = Form("")
):
    """Update a bug/task."""
    updates = {
        "summary": summary,
        "description": description,
        "type": type,
        "status": status,
        "severity": severity,
        "priority": priority,
        "additional_info": additional_info or ""
    }
    
    success = db.update_task(bug_id, updates)
    
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return RedirectResponse(
        url=f"/db/{database_id}/bug/{bug_id}",
        status_code=303
    )


@app.get("/db/{database_id}/bug/new", response_class=HTMLResponse)
async def bug_new(request: Request, database_id: str):
    """Form to create a new bug/task."""
    config = load_config()
    current_theme = db.get_setting('theme', 'default')
    
    return templates.TemplateResponse(
        "task_new.html",
        {
            "request": request,
            "config": config,
            "database_id": database_id,
            "current_theme": current_theme
        }
    )


@app.post("/db/{database_id}/bug/new")
async def bug_create(
    database_id: str,
    summary: str = Form(...),
    description: str = Form(...),
    type: str = Form("task"),
    severity: str = Form("Medium"),
    priority: str = Form("Medium"),
    additional_info: Optional[str] = Form("")
):
    """Create a new bug/task."""
    config = load_config()
    
    # Generate next bug ID
    bug_count = config.get('bug_count', 0) + 1
    bug_id = f"{bug_count:05d}"
    
    task_data = {
        "id": bug_id,
        "type": type,
        "detected_in": config.get('active_milestone', '1.0.0'),
        "fix_by_milestone": config.get('active_milestone', '1.0.0'),
        "severity": severity,
        "priority": priority,
        "status": "active",
        "summary": summary,
        "description": description,
        "additional_info": additional_info or "",
        "database_id": database_id
    }
    
    db.create_task(task_data)
    
    # Update bug count
    config['bug_count'] = bug_count
    save_config(config)
    
    return RedirectResponse(
        url=f"/db/{database_id}/bug/{bug_id}",
        status_code=303
    )


@app.post("/db/{database_id}/bug/{bug_id}/upload")
async def upload_file(
    database_id: str,
    bug_id: str,
    file: UploadFile = File(...)
):
    """Upload a file attachment to a bug/task."""
    task = db.get_task(bug_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Save file
    upload_dir = Path("uploads") / bug_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = upload_dir / file.filename
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # Add to database
    db.add_attachment(bug_id, file.filename, str(file_path))
    
    return RedirectResponse(
        url=f"/db/{database_id}/bug/{bug_id}",
        status_code=303
    )


@app.get("/api/tasks", response_class=dict)
async def api_tasks(database_id: Optional[str] = None):
    """API endpoint to get all tasks."""
    tasks = db.get_all_tasks(database_id=database_id)
    return {"tasks": tasks}


@app.get("/api/task/{task_id}", response_class=dict)
async def api_task(task_id: str):
    """API endpoint to get a specific task."""
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    attachments = db.get_attachments(task_id)
    return {"task": task, "attachments": attachments}


@app.get("/journal", response_class=HTMLResponse)
async def journal(request: Request):
    """Journal page showing stock portfolio data."""
    config = load_config()
    current_theme = db.get_setting('theme', 'default')
    
    # Get portfolio data from database
    portfolio_rows, symbols = db.get_portfolio_data()
    
    # Convert database rows to display format
    journal_data = []
    for row in portfolio_rows:
        display_row = {"Date": row['date']}
        for symbol in symbols:
            display_row[symbol] = row.get(symbol)
        journal_data.append(display_row)
    
    # Calculate max values for each column (excluding Date)
    max_values = {}
    if journal_data and symbols:
        for symbol in symbols:
            values = [row[symbol] for row in journal_data if row.get(symbol) is not None]
            max_values[symbol] = max(values) if values else 0
    
    return templates.TemplateResponse(
        "journal.html",
        {
            "request": request,
            "config": config,
            "journal_data": journal_data,
            "max_values": max_values,
            "columns": symbols,
            "current_theme": current_theme
        }
    )


@app.get("/daily-charts", response_class=HTMLResponse)
async def daily_charts(request: Request):
    """Daily charts page showing line charts for each tracked symbol."""
    config = load_config()
    current_theme = db.get_setting('theme', 'default')
    
    # Get chart data from database
    chart_data = db.get_chart_data()
    
    # Get all-time high statistics
    ath_stats = db.get_all_time_high_stats()
    
    return templates.TemplateResponse(
        "daily_charts.html",
        {
            "request": request,
            "config": config,
            "chart_data": chart_data,
            "ath_stats": ath_stats,
            "current_theme": current_theme
        }
    )


@app.get("/settings", response_class=HTMLResponse)
async def settings(request: Request):
    """Settings page for configuration and data management."""
    config = load_config()
    current_theme = db.get_setting('theme', 'default')
    
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "config": config,
            "current_theme": current_theme
        }
    )


@app.post("/settings/theme")
async def save_theme(theme: str = Form(...)):
    """Save theme preference to database."""
    valid_themes = ['default', 'high-visibility', 'ultra-contrast', 'light', 'light-high-contrast']
    
    if theme not in valid_themes:
        raise HTTPException(status_code=400, detail="Invalid theme")
    
    db.set_setting('theme', theme)
    
    return {"success": True, "theme": theme}


@app.get("/import-rules", response_class=HTMLResponse)
async def import_rules(request: Request):
    """Import Rules configuration page."""
    config = load_config()
    current_theme = db.get_setting('theme', 'default')
    
    # Get all import rules data
    symbol_mappings = db.get_symbol_mappings()
    auto_fetch_symbols = db.get_auto_fetch_symbols()
    calculated_columns = db.get_calculated_columns()
    excluded_symbols = db.get_excluded_symbols()
    value_scaling_rules = db.get_value_scaling_rules()
    
    return templates.TemplateResponse(
        "import_rules.html",
        {
            "request": request,
            "config": config,
            "current_theme": current_theme,
            "symbol_mappings": symbol_mappings,
            "auto_fetch_symbols": auto_fetch_symbols,
            "calculated_columns": calculated_columns,
            "excluded_symbols": excluded_symbols,
            "value_scaling_rules": value_scaling_rules
        }
    )


@app.post("/import-rules/symbol-mapping")
async def save_symbol_mapping(
    journal_symbol: str = Form(...),
    yahoo_symbol: str = Form(...),
    mapping_id: Optional[int] = Form(None)
):
    """Save or update a symbol mapping."""
    try:
        if mapping_id:
            # Update existing
            success = db.update_symbol_mapping(mapping_id, journal_symbol, yahoo_symbol)
            if not success:
                raise HTTPException(status_code=404, detail="Mapping not found")
        else:
            # Create new
            db.add_symbol_mapping(journal_symbol, yahoo_symbol)
        
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/import-rules/symbol-mapping/{mapping_id}")
async def delete_symbol_mapping(mapping_id: int):
    """Delete a symbol mapping."""
    success = db.delete_symbol_mapping(mapping_id)
    if not success:
        raise HTTPException(status_code=404, detail="Mapping not found")
    return {"success": True}


@app.post("/import-rules/auto-fetch")
async def save_auto_fetch(symbol: str = Form(...)):
    """Add a symbol to auto-fetch list."""
    try:
        db.add_auto_fetch_symbol(symbol)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/import-rules/auto-fetch/{symbol_id}/toggle")
async def toggle_auto_fetch(symbol_id: int, enabled: bool = Form(...)):
    """Toggle auto-fetch symbol enabled status."""
    success = db.toggle_auto_fetch_symbol(symbol_id, enabled)
    if not success:
        raise HTTPException(status_code=404, detail="Symbol not found")
    return {"success": True}


@app.delete("/import-rules/auto-fetch/{symbol_id}")
async def delete_auto_fetch(symbol_id: int):
    """Delete an auto-fetch symbol."""
    success = db.delete_auto_fetch_symbol(symbol_id)
    if not success:
        raise HTTPException(status_code=404, detail="Symbol not found")
    return {"success": True}


@app.post("/import-rules/calculated-column")
async def save_calculated_column(
    column_name: str = Form(...),
    calculation_type: str = Form(...),
    config_json: str = Form(...),
    column_id: Optional[int] = Form(None)
):
    """Save or update a calculated column."""
    try:
        config = json.loads(config_json)
        
        if column_id:
            # Update existing
            success = db.update_calculated_column(column_id, column_name, calculation_type, config)
            if not success:
                raise HTTPException(status_code=404, detail="Column not found")
        else:
            # Create new
            db.add_calculated_column(column_name, calculation_type, config)
        
        return {"success": True}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid config JSON")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/import-rules/calculated-column/{column_id}")
async def delete_calculated_column(column_id: int):
    """Delete a calculated column."""
    success = db.delete_calculated_column(column_id)
    if not success:
        raise HTTPException(status_code=404, detail="Column not found")
    return {"success": True}


@app.post("/import-rules/exclusion")
async def save_exclusion(
    symbol: str = Form(...),
    reason: str = Form("")
):
    """Add a symbol to the exclusion list."""
    try:
        db.add_excluded_symbol(symbol, reason)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/import-rules/exclusion/{exclusion_id}")
async def delete_exclusion(exclusion_id: int):
    """Delete a symbol exclusion."""
    success = db.delete_excluded_symbol(exclusion_id)
    if not success:
        raise HTTPException(status_code=404, detail="Exclusion not found")
    return {"success": True}


@app.post("/import-rules/value-scaling")
async def save_value_scaling(
    column_name: str = Form(...),
    digits_to_remove: int = Form(...),
    rule_id: Optional[int] = Form(None)
):
    """Save or update a value scaling rule."""
    try:
        if rule_id:
            # Update existing
            success = db.update_value_scaling_rule(rule_id, column_name, digits_to_remove)
            if not success:
                raise HTTPException(status_code=404, detail="Rule not found")
        else:
            # Create new
            db.add_value_scaling_rule(column_name, digits_to_remove)
        
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/import-rules/value-scaling/{rule_id}/toggle")
async def toggle_value_scaling(rule_id: int, enabled: bool = Form(...)):
    """Toggle value scaling rule enabled status."""
    success = db.toggle_value_scaling_rule(rule_id, enabled)
    if not success:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"success": True}


@app.delete("/import-rules/value-scaling/{rule_id}")
async def delete_value_scaling(rule_id: int):
    """Delete a value scaling rule."""
    success = db.delete_value_scaling_rule(rule_id)
    if not success:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"success": True}


@app.post("/journal/import")
async def import_journal_csv(file: UploadFile = File(...)):
    """Import portfolio data from CSV file."""
    try:
        # Read CSV file
        contents = await file.read()
        csv_text = contents.decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(csv_text))
        
        # Convert to list of dictionaries
        csv_data = list(csv_reader)
        
        # Import into database
        imported_count = db.import_portfolio_csv(csv_data)
        
        return RedirectResponse(
            url=f"/settings?imported={imported_count}",
            status_code=303
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error importing CSV: {str(e)}")


@app.post("/journal/import-holdings")
async def import_holdings_csv(file: UploadFile = File(...)):
    """Import stock holdings from account-based CSV file."""
    try:
        # Read CSV file
        contents = await file.read()
        csv_text = contents.decode('utf-8')
        
        # Parse CSV as list of lists (not DictReader)
        csv_reader = csv.reader(io.StringIO(csv_text))
        csv_data = list(csv_reader)
        
        # Import into database
        result = db.import_stock_holdings_csv(csv_data)
        
        if not result.get('success', False):
            error_msg = result.get('error', 'Unknown error')
            raise HTTPException(status_code=400, detail=error_msg)
        
        # Build detailed result message
        parts = []
        parts.append(f"{result['symbols_imported']} symbols")
        
        if result.get('csv_symbols'):
            parts.append(f"{len(result['csv_symbols'])} from CSV")
        if result.get('calculated_symbols'):
            parts.append(f"{len(result['calculated_symbols'])} calculated")
        if result.get('auto_fetched_symbols'):
            parts.append(f"{len(result['auto_fetched_symbols'])} auto-fetched")
        if result.get('excluded_symbols'):
            parts.append(f"{len(result['excluded_symbols'])} excluded")
        
        detail = ' (' + ', '.join(parts[1:]) + ')' if len(parts) > 1 else ''
        
        # Add warning count if any
        warning_param = ""
        if result.get('warnings'):
            warning_param = f"&warnings={len(result['warnings'])}"
        
        return RedirectResponse(
            url=f"/settings?holdings_imported={result['symbols_imported']}{detail}&date={result['date']}{warning_param}",
            status_code=303
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error importing holdings CSV: {str(e)}")


@app.post("/journal/reorder-columns")
async def reorder_columns(column_order: str = Form(...)):
    """Update the column order for portfolio display."""
    try:
        # Parse comma-separated column names
        symbols = [s.strip() for s in column_order.split(',') if s.strip()]
        
        # Update in database
        success = db.update_column_order(symbols)
        
        if success:
            return RedirectResponse(
                url="/journal?reordered=1",
                status_code=303
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to update column order")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reordering columns: {str(e)}")


@app.post("/journal/update-cell")
async def update_cell(
    date: str = Form(...),
    symbol: str = Form(...),
    value: str = Form(...)
):
    """Update a single cell value in the portfolio."""
    try:
        # Convert value to float
        float_value = float(value.replace('$', '').replace(',', '').strip()) if value.strip() else None
        
        # Update in database
        success = db.update_portfolio_value(date, symbol, float_value)
        
        if success:
            return {"success": True, "value": float_value}
        else:
            raise HTTPException(status_code=500, detail="Failed to update cell value")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid number format")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error updating cell: {str(e)}")


@app.post("/journal/update-date")
async def update_date(
    old_date: str = Form(...),
    new_date: str = Form(...)
):
    """Update a date in the portfolio."""
    try:
        success = db.update_portfolio_date(old_date, new_date)
        
        if success:
            return {"success": True, "date": new_date}
        else:
            raise HTTPException(status_code=500, detail="Failed to update date")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error updating date: {str(e)}")


@app.post("/journal/delete-date")
async def delete_date(date: str = Form(...)):
    """Delete a date and all its associated portfolio data."""
    try:
        success = db.delete_portfolio_date(date)
        
        if success:
            return {"success": True}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete date")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error deleting date: {str(e)}")


@app.post("/journal/fetch-price")
async def fetch_price(
    symbol: str = Form(...),
    date: str = Form(...)
):
    """Fetch stock price from Yahoo Finance for a given symbol and date.
    
    Uses symbol mapping from database if available.
    """
    try:
        result = fetch_yahoo_price(symbol, date, db)
        
        if result is None:
            raise HTTPException(status_code=404, detail=f"No price data found for {symbol}")
        
        return {
            "success": True,
            "price": result['price'],
            "symbol": symbol,
            "yahoo_symbol": result['yahoo_symbol'],
            "date": result['date']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching price: {str(e)}")


@app.post("/journal/add-symbol")
async def add_symbol(symbol: str = Form(...)):
    """Add a new symbol column to the portfolio."""
    try:
        # Validate symbol name
        symbol = symbol.strip().upper()
        if not symbol:
            return RedirectResponse(
                url="/journal?error=Symbol+cannot+be+empty",
                status_code=303
            )
        
        # Check if symbol already exists
        _, existing_symbols = db.get_portfolio_data()
        if symbol in existing_symbols:
            return RedirectResponse(
                url=f"/journal?error=Symbol+'{symbol}'+already+exists",
                status_code=303
            )
        
        # Add symbol to database with appropriate column order
        success = db.add_new_symbol(symbol)
        
        if success:
            return RedirectResponse(
                url="/journal?symbol_added=1",
                status_code=303
            )
        else:
            return RedirectResponse(
                url="/journal?error=Failed+to+add+symbol",
                status_code=303
            )
    except Exception as e:
        return RedirectResponse(
            url=f"/journal?error=Error+adding+symbol:+{str(e)}",
            status_code=303
        )


@app.post("/journal/remove-symbol")
async def remove_symbol(symbol: str = Form(...)):
    """Remove a symbol column from the portfolio."""
    try:
        # Validate symbol name
        symbol = symbol.strip().upper()
        if not symbol:
            return RedirectResponse(
                url="/journal?error=Symbol+cannot+be+empty",
                status_code=303
            )
        
        # Check if symbol exists
        _, existing_symbols = db.get_portfolio_data()
        if symbol not in existing_symbols:
            return RedirectResponse(
                url=f"/journal?error=Symbol+'{symbol}'+not+found",
                status_code=303
            )
        
        # Remove symbol from database
        success = db.remove_symbol(symbol)
        
        if success:
            return RedirectResponse(
                url=f"/journal?symbol_removed={symbol}",
                status_code=303
            )
        else:
            return RedirectResponse(
                url="/journal?error=Failed+to+remove+symbol",
                status_code=303
            )
    except Exception as e:
        return RedirectResponse(
            url=f"/journal?error=Error+removing+symbol:+{str(e)}",
            status_code=303
        )


@app.post("/journal/add-retroactive-date")
async def add_retroactive_date(date: str = Form(...), background_tasks: BackgroundTasks = None):
    """Add closing prices for all tracked symbols for a specific retroactive date.
    
    Args:
        date: Date in YYYY-MM-DD format
    
    Returns:
        JSON with number of symbols fetched
    """
    try:
        # Parse date
        try:
            date_obj = datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        # Format date with day name
        formatted_date = date_obj.strftime('%a %Y-%m-%d')
        
        # Reset progress log and mark as running
        fetch_progress_state["log"] = []
        fetch_progress_state["in_progress"] = True

        # Ensure the portfolio date row exists for this date (needed for DB upserts)
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                    INSERT OR IGNORE INTO portfolio_dates (date, imported_at)
                    VALUES (?, ?)
                """,
                (formatted_date, datetime.now().isoformat())
            )
            conn.commit()
        finally:
            conn.close()

        # Get all currently tracked symbols
        _, existing_symbols = db.get_portfolio_data()
        
        if not existing_symbols:
            raise HTTPException(status_code=400, detail="No symbols are currently tracked")
        
        # Filter out calculated columns and excluded symbols
        calculated_columns = db.get_calculated_columns()
        calculated_column_names = {col['column_name'] for col in calculated_columns}
        excluded_symbols_list = db.get_excluded_symbols()
        excluded_symbol_names = {sym['symbol'] for sym in excluded_symbols_list}
        
        # Common non-stock column names that should never be fetched
        non_stock_columns = {
            'Total', 'total', 'TOTAL',
            'Cash', 'cash', 'CASH',
            'E-Trade', 'e-trade', 'E-TRADE', 'etrade', 'ETRADE',
            'Subtotal', 'subtotal', 'SUBTOTAL',
            'Sum', 'sum', 'SUM'
        }
        
        # Filter symbols to only fetch actual stock tickers
        symbols_to_fetch = [
            symbol for symbol in existing_symbols 
            if symbol not in calculated_column_names 
            and symbol not in excluded_symbol_names
            and symbol not in non_stock_columns
        ]
        
        if not symbols_to_fetch:
            raise HTTPException(status_code=400, detail="No stock symbols to fetch (all are calculated or excluded)")
        
        # Work function to run in background so the request can return immediately
        def _do_work():
            symbols_fetched_local = 0
            failed_symbols_local = []
            fetch_log_local = []
            fetch_progress_state["total"] = len(symbols_to_fetch)
            fetch_progress_state["processed"] = 0
            for symbol in symbols_to_fetch:
                # Progress: announce attempt
                attempt_msg = f"… Fetching {symbol} for {formatted_date}"
                print(f"  {attempt_msg}")
                fetch_progress_state["log"].append(attempt_msg)
                result = fetch_yahoo_price(symbol, formatted_date, db)
                if result:
                    # Update portfolio value for this date and symbol
                    # Ensure date row exists (defensive in case of race/rollback)
                    try:
                        conn2 = db.get_connection()
                        cur2 = conn2.cursor()
                        cur2.execute(
                            """
                                INSERT OR IGNORE INTO portfolio_dates (date, imported_at)
                                VALUES (?, ?)
                            """,
                            (formatted_date, datetime.now().isoformat())
                        )
                        conn2.commit()
                    finally:
                        conn2.close()

                    success = db.update_portfolio_value(formatted_date, symbol, result['price'])
                    if success:
                        symbols_fetched_local += 1
                        log_entry = f"✓ Fetched {symbol}: ${result['price']:.2f}"
                        if result.get('yahoo_symbol') and result['yahoo_symbol'] != symbol:
                            log_entry += f" (using {result['yahoo_symbol']})"
                        fetch_log_local.append(log_entry)
                        print(f"  {log_entry}")
                        fetch_progress_state["log"].append(log_entry)
                    else:
                        fail_msg = f"{symbol} (database error)"
                        failed_symbols_local.append(fail_msg)
                        err_entry = f"✗ Failed {symbol}: database error"
                        fetch_log_local.append(err_entry)
                        fetch_progress_state["log"].append(err_entry)
                else:
                    fail_msg = f"{symbol} (no data)"
                    failed_symbols_local.append(fail_msg)
                    err_entry = f"✗ Failed {symbol}: no data from Yahoo Finance"
                    fetch_log_local.append(err_entry)
                    fetch_progress_state["log"].append(err_entry)
                    print(f"  ✗ Failed to fetch {symbol}")
                # update processed count visible to clients
                fetch_progress_state["processed"] = fetch_progress_state.get("processed", 0) + 1

            # Write summary
            # Summary stored for client; message used only for logs
            result_message = f"Fetched {symbols_fetched_local}/{len(symbols_to_fetch)} symbols"
            if failed_symbols_local:
                result_message += f". Failed: {', '.join(failed_symbols_local)}"
            fetch_progress_state["in_progress"] = False
            fetch_progress_state["result"] = {
                "symbols_fetched": symbols_fetched_local,
                "total_symbols": len(symbols_to_fetch)
            }

        # Kick off background work; always use a threadpool so POST returns immediately
        background_tasks.add_task(_do_work)
        # Return ACK; UI will stream/poll for progress and completion
        return {
            "success": True,
            "started": True,
            "date": formatted_date,
            "total_symbols": len(symbols_to_fetch),
            "skipped_symbols": [s for s in existing_symbols if s not in symbols_to_fetch]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        fetch_progress_state["in_progress"] = False
        fetch_progress_state["result"] = None
        raise HTTPException(status_code=500, detail=f"Error adding retroactive date: {str(e)}")


@app.post("/import-rules/backfill")
async def backfill_historical_data(
    symbol: str = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    overwrite: bool = Form(False)
):
    """Backfill historical data for a symbol over a specified date range.
    
    Args:
        symbol: Stock symbol to backfill (will use symbol mapping if available)
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        overwrite: If True, replace existing data; if False, only fill missing data
    
    Returns:
        JSON with number of days imported and date range
    """
    try:
        symbol = symbol.strip().upper()
        
        if not symbol:
            raise HTTPException(status_code=400, detail="Symbol cannot be empty")
        
        # Parse dates
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start date format. Use YYYY-MM-DD")
        
        try:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end date format. Use YYYY-MM-DD")
        
        # Validate date range
        if end_date_obj < start_date_obj:
            raise HTTPException(status_code=400, detail="End date must be after start date")
        
        # Check for symbol mapping
        yahoo_symbol = db.get_symbol_mapping(symbol)
        if not yahoo_symbol:
            yahoo_symbol = symbol
        
        mode_str = "overwrite mode" if overwrite else "preserve mode"
        print(f"Backfilling {symbol} (Yahoo: {yahoo_symbol}) from {start_date} to {end_date} ({mode_str})")
        
        # Fetch historical data using yfinance
        if yf is None:
            raise HTTPException(status_code=500, detail="yfinance not installed")
        
        ticker = yf.Ticker(yahoo_symbol)
        
        # Fetch history with a buffer
        hist = ticker.history(
            start=start_date_obj.strftime('%Y-%m-%d'),
            end=(end_date_obj + timedelta(days=1)).strftime('%Y-%m-%d')
        )
        
        if hist.empty:
            raise HTTPException(
                status_code=404,
                detail=f"No historical data found for {symbol} (tried {yahoo_symbol})"
            )
        
        # Get existing symbols to determine column order
        _, existing_symbols = db.get_portfolio_data()
        
        # Insert data for each trading day
        days_imported = 0
        overwritten_count = 0
        first_date = None
        last_date = None
        
        for date_index, row in hist.iterrows():
            trading_date = date_index.strftime('%a %Y-%m-%d')
            close_price = float(row['Close'])
            # update processed count visible to clients
            fetch_progress_state["processed"] = fetch_progress_state.get("processed", 0) + 1
            
            if first_date is None:
                first_date = trading_date
            last_date = trading_date
            
            # Add symbol to portfolio if it doesn't exist
            if symbol not in existing_symbols:
                db.add_new_symbol(symbol)
                existing_symbols.append(symbol)
            
            # Update or insert the price for this date
            # First, ensure the date exists in portfolio_dates
            conn = db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR IGNORE INTO portfolio_dates (date, imported_at)
                VALUES (?, ?)
            """, (trading_date, datetime.now().isoformat()))
            
            cursor.execute("SELECT id FROM portfolio_dates WHERE date = ?", (trading_date,))
            date_id_row = cursor.fetchone()
            if date_id_row:
                date_id = date_id_row[0]
                
                # Check if this symbol already has a value for this date
                cursor.execute("""
                    SELECT value FROM portfolio_holdings
                    WHERE date_id = ? AND symbol = ?
                """, (date_id, symbol))
                
                existing_value_row = cursor.fetchone()
                existing_value = existing_value_row[0] if existing_value_row else None
                
                # Get column order for this symbol
                column_order = existing_symbols.index(symbol) if symbol in existing_symbols else len(existing_symbols)
                
                if overwrite:
                    # Overwrite mode: always update the value
                    if existing_value is not None:
                        overwritten_count += 1
                    
                    cursor.execute("""
                        INSERT INTO portfolio_holdings (date_id, symbol, value, column_order)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(date_id, symbol) 
                        DO UPDATE SET value = ?
                    """, (date_id, symbol, close_price, column_order, close_price))
                    
                    days_imported += 1
                else:
                    # Preserve mode: only insert if no existing value or value is NULL
                    if not existing_value_row or existing_value is None:
                        cursor.execute("""
                            INSERT INTO portfolio_holdings (date_id, symbol, value, column_order)
                            VALUES (?, ?, ?, ?)
                            ON CONFLICT(date_id, symbol) 
                            DO UPDATE SET value = CASE WHEN value IS NULL THEN ? ELSE value END
                        """, (date_id, symbol, close_price, column_order, close_price))
                        
                        days_imported += 1
            
            conn.commit()
            conn.close()
        
        return {
            "success": True,
            "symbol": symbol,
            "yahoo_symbol": yahoo_symbol,
            "days_imported": days_imported,
            "overwritten_count": overwritten_count,
            "start_date": first_date,
            "end_date": last_date
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error backfilling data: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    import platform
    
    # Detect platform for displaying correct URL
    is_windows = platform.system() == "Windows"
    display_host = "localhost" if is_windows else "0.0.0.0"
    
    # Print startup message with correct URL for platform
    print("\n" + "="*60)
    print("Starting Stock Tracker Server")
    print("="*60)
    print(f"Server running at: http://{display_host}:8000")
    print(f"Platform: {platform.system()}")
    print("Press CTRL+C to quit")
    print("="*60 + "\n")
    
    # Run server (still bind to 0.0.0.0 to allow network access)
    uvicorn.run(app, host="0.0.0.0", port=8000)

