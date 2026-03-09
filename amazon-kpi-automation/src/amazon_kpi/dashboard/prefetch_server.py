"""Lightweight HTTP server for cron-job.org to trigger data pre-fetch.

Runs as a separate Cloud Run service. Validates requests using an API key
passed as a query parameter or header.

Run locally: python -m amazon_kpi.dashboard.prefetch_server
Deploy: see docker/Dockerfile.prefetch and infrastructure/cloudbuild-prefetch-job.yaml
"""

from __future__ import annotations

import os
import sys
import traceback

from flask import Flask, jsonify, request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

PREFETCH_API_KEY = os.environ.get("CRONJOB_API_KEY", "")


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "amazon-kpi-prefetch"})


@app.route("/prefetch", methods=["GET", "POST"])
def prefetch():
    """Trigger data pre-fetch. Called by cron-job.org hourly."""
    # Validate API key
    api_key = request.args.get("key") or request.headers.get("X-API-Key", "")
    if not PREFETCH_API_KEY or api_key != PREFETCH_API_KEY:
        return jsonify({"error": "unauthorized"}), 401

    try:
        from amazon_kpi.dashboard.prefetch import prefetch as run_prefetch
        run_prefetch()
        return jsonify({"status": "ok", "message": "prefetch complete"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e), "trace": traceback.format_exc()}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
