"""
FastAPI server for the Stock Tracker application.
"""
import os
import csv
import io
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from models import Database, load_config, save_config


app = FastAPI(title="Inspector - Bug Tracking System")

# Setup templates and static files
templates = Jinja2Templates(directory="templates")
os.makedirs("static", exist_ok=True)
os.makedirs("uploads", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Initialize database
db = Database()


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
    
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "config": config,
            "stats": stats,
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
    
    return RedirectResponse(
        url="/settings?theme_saved=1",
        status_code=303
    )


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
        
        if 'error' in result:
            raise HTTPException(status_code=400, detail=result['error'])
        
        return RedirectResponse(
            url=f"/settings?holdings_imported={result['symbols_imported']}&date={result['date']}",
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

