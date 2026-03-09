"""Register the hourly prefetch cron job on cron-job.org.

Usage:
    python scripts/setup_cronjob.py <PREFETCH_SERVICE_URL>

Example:
    python scripts/setup_cronjob.py https://amazon-kpi-prefetch-xxxxx-ew.a.run.app

This creates an hourly cron job on cron-job.org that calls:
    <PREFETCH_SERVICE_URL>/prefetch?key=<CRONJOB_API_KEY>
"""

import json
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/setup_cronjob.py <PREFETCH_SERVICE_URL>")
        print("Example: python scripts/setup_cronjob.py https://amazon-kpi-prefetch-xxxxx-ew.a.run.app")
        sys.exit(1)

    prefetch_url = sys.argv[1].rstrip("/")
    api_key = os.environ.get("CRONJOB_API_KEY", "")

    if not api_key:
        print("Error: CRONJOB_API_KEY not found in .env")
        sys.exit(1)

    # cron-job.org API
    cronjob_api = "https://api.cron-job.org"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    # Create the cron job
    job_data = {
        "job": {
            "url": f"{prefetch_url}/prefetch?key={api_key}",
            "title": "Amazon KPI Data Pre-fetch",
            "enabled": True,
            "saveResponses": True,
            "schedule": {
                "timezone": "Europe/Rome",
                # Every hour at minute 0
                "minutes": [0],
                "hours": [-1],      # -1 = every hour
                "mdays": [-1],      # -1 = every day
                "months": [-1],     # -1 = every month
                "wdays": [-1],      # -1 = every weekday
            },
            "requestTimeout": 300,  # 5 min timeout
            "requestMethod": 1,     # 1 = GET
            "notification": {
                "onFailure": True,
                "onSuccess": False,
                "onDisable": True,
            },
        }
    }

    print(f"Creating cron job on cron-job.org...")
    print(f"  URL: {prefetch_url}/prefetch?key=***")
    print(f"  Schedule: every hour at :00")
    print(f"  Timezone: Europe/Rome")

    resp = requests.put(f"{cronjob_api}/jobs", headers=headers, json=job_data)

    if resp.status_code in (200, 201):
        result = resp.json()
        job_id = result.get("jobId", "unknown")
        print(f"\nCron job created successfully! Job ID: {job_id}")
        print(f"Manage at: https://cron-job.org/en/members/jobs/")
    else:
        print(f"\nError creating cron job: {resp.status_code}")
        print(resp.text)
        sys.exit(1)


if __name__ == "__main__":
    main()
