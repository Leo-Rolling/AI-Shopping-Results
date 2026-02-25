# Amazon Weekly KPI Automation

Automated KPI extraction from Sellerboard and Google Sheets reporting for Amazon marketplaces.

## Features

- Scrapes KPI data from Sellerboard using Playwright browser automation
- Processes data for 7 Amazon marketplaces (US, CA, UK, DE, IT, FR, ES)
- Supports 8 product categories
- Generates formatted Google Sheets reports
- Runs weekly on Google Cloud Run triggered by Cloud Scheduler

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.11+ |
| Web Scraping | Playwright (async) |
| Data Processing | Pydantic, Pandas |
| Google APIs | gspread, google-api-python-client |
| Secrets | Google Secret Manager |
| Deployment | Google Cloud Run (containerized) |
| Scheduling | Google Cloud Scheduler |
| HTTP Server | Flask + Gunicorn |

## Project Structure

```
amazon-kpi-automation/
├── src/amazon_kpi/
│   ├── main.py                    # Cloud Run entry point (Flask app)
│   ├── config/
│   │   ├── constants.py           # Marketplaces, KPI names, regions
│   │   └── sku_categories.py      # Category → SKU mappings
│   ├── scraper/
│   │   ├── sellerboard_client.py  # Main scraper orchestrator
│   │   ├── auth.py                # Login/session management
│   │   ├── navigation.py          # Page navigation, filters
│   │   └── extractors.py          # KPI value extraction
│   ├── processing/
│   │   ├── models.py              # Pydantic data models
│   │   ├── aggregator.py          # Regional aggregation
│   │   └── comparator.py          # Week-over-week calculations
│   ├── output/
│   │   ├── sheets_client.py       # Google Sheets API wrapper
│   │   ├── formatters.py          # Currency, percentage formatting
│   │   └── templates.py           # Sheet layout definitions
│   ├── secrets/
│   │   └── secret_manager.py      # GCP Secret Manager client
│   └── utils/
│       ├── exceptions.py          # Custom exceptions
│       └── retry.py               # Retry decorators
├── docker/
│   └── Dockerfile
├── infrastructure/
│   └── cloudbuild.yaml
├── pyproject.toml
└── .env.example
```

## Setup

### Prerequisites

- Python 3.11+
- Google Cloud SDK (`gcloud`)
- Docker (for containerized deployment)

### Local Development

1. Clone the repository:
   ```bash
   cd amazon-kpi-automation
   ```

2. Create virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -e ".[dev]"
   playwright install chromium
   ```

4. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

5. Run locally:
   ```bash
   # Run extraction
   python -m amazon_kpi --run

   # Start development server
   python -m amazon_kpi --server

   # Test connections
   python -m amazon_kpi --test
   ```

### Google Cloud Setup

1. Authenticate with GCP:
   ```bash
   gcloud auth login
   gcloud config set project sellerboard-amz-kpi
   gcloud auth application-default login
   ```

2. Enable required APIs:
   ```bash
   gcloud services enable \
     secretmanager.googleapis.com \
     sheets.googleapis.com \
     drive.googleapis.com \
     run.googleapis.com \
     cloudbuild.googleapis.com \
     cloudscheduler.googleapis.com
   ```

3. Create service accounts:
   ```bash
   # Runner service account (for Cloud Run)
   gcloud iam service-accounts create amazon-kpi-runner \
     --display-name="Amazon KPI Runner"

   # Scheduler service account
   gcloud iam service-accounts create amazon-kpi-scheduler \
     --display-name="Amazon KPI Scheduler"
   ```

4. Create secrets:
   ```bash
   # Sellerboard credentials
   echo '{"email": "your-email", "password": "your-password"}' | \
     gcloud secrets create sellerboard-credentials --data-file=-

   # Google service account key
   gcloud secrets create google-service-account \
     --data-file=/path/to/service-account.json

   # Drive folder ID
   echo -n "1QR55nVzPpY9bUMzydI7CkSMPY4HLPGzM" | \
     gcloud secrets create google-drive-folder-id --data-file=-
   ```

5. Grant permissions:
   ```bash
   # Secret access for runner
   gcloud secrets add-iam-policy-binding sellerboard-credentials \
     --member="serviceAccount:amazon-kpi-runner@PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/secretmanager.secretAccessor"
   ```

### Deployment

Deploy using Cloud Build:

```bash
gcloud builds submit --config=infrastructure/cloudbuild.yaml
```

Or build and deploy manually:

```bash
# Build
docker build -t gcr.io/PROJECT_ID/amazon-kpi-automation -f docker/Dockerfile .

# Push
docker push gcr.io/PROJECT_ID/amazon-kpi-automation

# Deploy
gcloud run deploy amazon-kpi-automation \
  --image gcr.io/PROJECT_ID/amazon-kpi-automation \
  --region europe-west1 \
  --memory 2Gi \
  --cpu 2 \
  --timeout 900 \
  --concurrency 1 \
  --no-allow-unauthenticated
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/run` | POST | Trigger KPI extraction |
| `/test` | GET | Test connections |

## Configuration

### Required GCP Secrets

| Secret Name | Content |
|-------------|---------|
| `sellerboard-credentials` | `{"email": "...", "password": "..."}` |
| `google-service-account` | Full service account JSON |
| `google-drive-folder-id` | Target Drive folder ID |

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GCP_PROJECT_ID` | Google Cloud project ID | - |
| `USE_ENV_SECRETS` | Use env vars instead of Secret Manager | `false` |
| `PORT` | HTTP server port | `8080` |
| `HEADLESS` | Run browser in headless mode | `true` |

## KPIs Extracted

- Gross Sales
- Units Sold
- Orders
- Refunds
- Refund Rate
- Promo Rebates
- Amazon Costs
- COGS
- Net Profit
- Margin
- ROI
- Ad Spend
- ACOS
- TACOS

## Marketplaces

- US (amazon.com)
- CA (amazon.ca)
- UK (amazon.co.uk)
- DE (amazon.de)
- IT (amazon.it)
- FR (amazon.fr)
- ES (amazon.es)

## Regional Aggregation

- **EU+UK**: Sum of UK + DE + IT + FR + ES (EUR)
- **US+CA**: Sum of US + CA (USD)
- **Total**: EU+UK (converted to USD @ 1.08) + US+CA

## Output

Reports are saved to Google Drive as:
`AMZ_Meeting_KPIs DD Month YYYY`

Two sheets:
1. **KPIs**: Regional summary by category
2. **By Country**: Per-marketplace breakdown

## Troubleshooting

### Browser Issues

If Playwright fails to launch:
```bash
playwright install chromium
playwright install-deps chromium
```

### Authentication Errors

Verify secrets are accessible:
```bash
gcloud secrets versions access latest --secret=sellerboard-credentials
```

### Timeout Errors

The extraction can take 10-15 minutes. Ensure Cloud Run timeout is set to 900s.

## License

MIT
