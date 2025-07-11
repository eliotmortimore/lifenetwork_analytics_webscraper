from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import psycopg2
import os
from datetime import datetime
import subprocess
from apscheduler.schedulers.background import BackgroundScheduler

app = FastAPI()

# Allow CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db_conn():
    return psycopg2.connect(dbname='golife_analytics', user=os.getenv('USER'))

@app.get("/total_accounts")
def get_total_accounts():
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT scraped_at, total_accounts FROM total_accounts ORDER BY scraped_at DESC LIMIT 1;")
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        return {"scraped_at": row[0], "total_accounts": row[1]}
    return {"scraped_at": None, "total_accounts": None}

@app.get("/premium_subscribers")
def get_premium_subscribers(start: Optional[str] = None, end: Optional[str] = None):
    conn = get_db_conn()
    cur = conn.cursor()
    query = "SELECT scraped_at, valid_memberships, active_memberships, trial_memberships, canceled_memberships, past_due_memberships FROM premium_subscribers"
    params = []
    if start and end:
        query += " WHERE scraped_at BETWEEN %s AND %s"
        params = [start, end]
    query += " ORDER BY scraped_at DESC"
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {
            "scraped_at": r[0],
            "valid_memberships": r[1],
            "active_memberships": r[2],
            "trial_memberships": r[3],
            "canceled_memberships": r[4],
            "past_due_memberships": r[5],
        }
        for r in rows
    ]

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
# 1. pip install fastapi uvicorn psycopg2-binary
# 2. python3 -m uvicorn dashboard_api:app --reload
#
# The API docs will be available at http://127.0.0.1:8000/docs 