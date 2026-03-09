"""Entry point for the Streamlit KPI dashboard.

Run with: streamlit run streamlit_app.py
"""

import os
import sys

# Ensure the src directory is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Load .env for local development
from dotenv import load_dotenv
load_dotenv()

from amazon_kpi.dashboard.app import main

if __name__ == "__main__":
    main()
else:
    # Streamlit runs the module directly (not via __main__)
    main()
