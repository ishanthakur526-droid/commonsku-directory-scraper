# CommonSKU Directory Scraper

A Python scraper that extracts the full company and contact directory from [CommonSKU's Social platform](https://social.commonsku.com) via their REST API.

## Overview

CommonSKU is a B2B platform used by promotional products distributors and suppliers. This project scrapes their social directory to collect structured company and contact data — including names, titles, emails, phone numbers, and addresses — across **1,010+ companies** and **7,200+ contacts**.

## Architecture

```
CommonSKU API
     │
     ├── GET /v1/company          → Full company list (~1,000 companies)
     │
     ├── GET /v1/user             → Users per company (names, emails, titles)
     │
     └── GET /v1/contact/toc      → Contact info per company (address, phone)
     │
     ▼
┌─────────────┐    ┌──────────────┐    ┌─────────────────┐
│  Fetch all   │───▶│ Merge users  │───▶│  Deduplicate &  │
│  companies   │    │ + contacts   │    │  export CSV/JSONL│
└─────────────┘    └──────────────┘    └─────────────────┘
```

## Key Features

- **API-first approach** — Hits CommonSKU's REST endpoints directly instead of scraping HTML, making it fast and reliable
- **Concurrent execution** — Uses a 10-thread `ThreadPoolExecutor` to scrape ~1,000 companies in parallel
- **Smart deduplication** — When duplicate records are found, keeps the one with the most complete data (score-based)
- **Defensive parsing** — Handles multiple API response shapes with fallback key lookups
- **Dual output** — Exports to both CSV and JSONL formats

## Data Fields

| Field | Description |
|-------|-------------|
| `company_name` | Name of the company |
| `first_name` | Contact's first name |
| `last_name` | Contact's last name |
| `professional_title` | Job title / role |
| `email` | Email address |
| `phone` | Phone number |
| `company_address` | Full company address |
| `profile_url` | CommonSKU profile URL |
| `company_id` | Unique company identifier |

## Results

| Metric | Count |
|--------|-------|
| Companies scraped | **1,012** |
| Contacts extracted | **7,298** |
| Records with email | ~98% |
| Records with phone | ~46% |

## Setup & Usage

### Prerequisites

- Python 3.8+

```bash
pip install -r requirements.txt
```

### Running the Scraper

1. Obtain a JWT Bearer token by logging into CommonSKU
2. Set it as an environment variable:

```bash
# Windows
set COMMONSKU_TOKEN=your_jwt_token_here

# Linux / Mac
export COMMONSKU_TOKEN=your_jwt_token_here
```

3. Run the scraper:

```bash
python scrape.py
```

4. Output files will be generated in the same directory:
   - `commonsku_directory_v2.csv`
   - `commonsku_directory_v2.jsonl`

### Verifying the Data

```bash
python verify_data.py
```

This prints a summary of field coverage, duplicate detection, and sample rows.

## Sample Output

```
==================================================
DONE
==================================================
Companies in API:   1012
Companies scraped:  1012
People (deduped):   7298
Errors:             0
With email:         7186
With phone:         3397
With address:       2324
```

## File Structure

```
commonsku-directory-scraper/
├── scrape.py              # Main scraper script
├── verify_data.py         # Data verification & quality checks
├── requirements.txt       # Python dependencies
├── README.md
├── .gitignore
└── sample_output.csv      # (optional) Small sample of output
```

## Technical Notes

- The scraper makes 2 API calls per company (users + contacts), so ~2,000 total requests
- Rate limiting is handled implicitly by the thread pool (10 concurrent workers)
- JWT tokens from CommonSKU expire after ~7 days
- The deduplication key is `(company_id, profile_url)` — duplicate records are resolved by keeping the one with more non-empty fields
- **Data Nuance (1,012 vs 1,010 Companies):** The dataset correctly contains 1,012 unique `company_id`s. However, two companies ("Genumark" and "Halo") each have two separate, distinct entries in the CommonSKU directory. A unique count on `company_name` yields 1,010, while `company_id` yields 1,012.

## License

This project is for educational and portfolio purposes only. The scraped data belongs to CommonSKU and the respective companies listed in their directory.
