from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import os
from datetime import datetime
import subprocess
from apscheduler.schedulers.background import BackgroundScheduler
import csv
import glob

app = FastAPI()

# Allow CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_latest_csv_data(directory: str, filename_pattern: str):
    """Get the latest data from CSV files"""
    pattern = os.path.join(directory, filename_pattern)
    files = glob.glob(pattern)
    if not files:
        return None
    
    # Get the most recent file
    latest_file = max(files, key=os.path.getctime)
    
    try:
        with open(latest_file, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            if rows:
                return rows[0]  # Return the first (and only) row
    except Exception as e:
        print(f"Error reading {latest_file}: {e}")
        return None
    
    return None

@app.get("/total_accounts")
def get_total_accounts():
    data = get_latest_csv_data("total_accounts", "total_accounts_*.csv")
    if data:
        return {
            "scraped_at": data.get("scraped_at"),
            "total_accounts": int(data.get("total_accounts", 0))
        }
    return {"scraped_at": None, "total_accounts": None}

@app.get("/premium_subscribers")
def get_premium_subscribers(start: Optional[str] = None, end: Optional[str] = None):
    data = get_latest_csv_data("premium_subscribers", "premium_subscribers_*.csv")
    if data:
        return [{
            "scraped_at": data.get("scraped_at"),
            "valid_memberships": int(data.get("valid_memberships", 0)),
            "active_memberships": int(data.get("active_memberships", 0)),
            "trial_memberships": int(data.get("trial_memberships", 0)),
            "canceled_memberships": int(data.get("canceled_memberships", 0)),
            "past_due_memberships": int(data.get("past_due_memberships", 0)),
        }]
    return []

@app.post("/refresh")
def refresh_data():
    try:
        # Run the webscraper as a subprocess
        result = subprocess.run(["python", "app.py"], capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            return {"status": "success", "output": result.stdout}
        else:
            return {"status": "error", "output": result.stderr}
    except Exception as e:
        return {"status": "error", "output": str(e)}

def run_scraper_job():
    try:
        subprocess.run(["python", "app.py"], capture_output=True, text=True, timeout=300)
    except Exception as e:
        print(f"Scheduled scrape failed: {e}")

# Start scheduler on app startup
def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_scraper_job, 'interval', hours=6, next_run_time=None)
    scheduler.start()

start_scheduler()

# Instructions to run:
# 1. pip install fastapi uvicorn
# 2. python3 -m uvicorn dashboard_api:app --reload
#
# The API docs will be available at http://127.0.0.1:8000/docs 