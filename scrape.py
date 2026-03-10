"""
CommonSKU Directory Scraper — Pure API approach
Pulls the full company list from the API, then fetches users + contacts for each.
"""
import requests, csv, json, time, os, sys
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = "https://social.commonsku.com"
TOKEN = os.environ.get("COMMONSKU_TOKEN", "")
if not TOKEN:
    print("ERROR: Set the COMMONSKU_TOKEN environment variable before running.")
    print("  e.g.  set COMMONSKU_TOKEN=your_jwt_token_here   (Windows)")
    print("  e.g.  export COMMONSKU_TOKEN=your_jwt_token_here (Linux/Mac)")
    sys.exit(1)
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

session = requests.Session()
session.headers.update(HEADERS)

# ── 1. Get ALL companies ──────────────────────────────────────
print("Fetching company list...")
r = session.get(f"{BASE}/v1/company", params={"on_csku_only": "true"})
r.raise_for_status()
data = r.json()

# The API might nest them under a key — handle both shapes
if isinstance(data, list):
    companies = data
elif isinstance(data, dict):
    companies = data.get("companies", data.get("data", data.get("results", [])))
    if not isinstance(companies, list):
        # dump keys so we can debug
        print(f"Unexpected response shape. Keys: {list(data.keys())}")
        print(f"First 500 chars: {json.dumps(data)[:500]}")
        sys.exit(1)

print(f"Got {len(companies)} companies")

# Extract id, name, type from each company object
company_list = []
for c in companies:
    cid = c.get("company_id") or c.get("id") or c.get("uuid", "")
    cname = c.get("company_name") or c.get("name", "")
    ctype = c.get("company_type") or c.get("type", "DISTRIBUTOR")
    company_list.append({"id": cid, "name": cname, "type": ctype})

print(f"Parsed {len(company_list)} companies. First 3: {[c['name'] for c in company_list[:3]]}")

# ── 2. Scrape users + contacts per company ────────────────────
rows = []
errors = []

def scrape_company(c):
    """Fetch users and contacts for one company. Returns list of row dicts."""
    cid, cname, ctype = c["id"], c["name"], c["type"]
    result_rows = []
    try:
        # Users
        ur = session.get(f"{BASE}/v1/user", params={
            "search_type": "company-users",
            "company_id": cid,
            "company_type": "TENANT",
            "include_user": "true"
        }, timeout=15)
        users = ur.json().get("companyUsers", []) if ur.status_code == 200 else []

        # Contacts (address + phone)
        cr = session.get(f"{BASE}/v1/contact/toc", params={
            "parent_id": cid,
            "parent_type": ctype
        }, timeout=15)
        contacts = cr.json().get("contacts", []) if cr.status_code == 200 else []

        # Build address from first contact
        address, phone = "", ""
        if contacts:
            ct = contacts[0]
            parts = [ct.get("address_line_1"), ct.get("address_line_2"),
                     ct.get("address_city"), ct.get("address_state"),
                     ct.get("address_zip"), ct.get("address_country")]
            address = ", ".join(p for p in parts if p)
            phone = ct.get("primary_phone_number", "")

        for u in users:
            result_rows.append({
                "company_name": cname,
                "first_name": u.get("user_first_name", ""),
                "last_name": u.get("user_last_name", ""),
                "professional_title": u.get("position", "") or u.get("title", ""),
                "email": (u.get("user_email") or "").strip().lower(),
                "phone": u.get("phone") or u.get("primary_phone_number") or phone,
                "company_address": address,
                "profile_url": f"{BASE}/user.php?id={u.get('user_id', '')}",
                "company_id": cid,
            })
    except Exception as e:
        return cname, cid, str(e), []
    return cname, cid, None, result_rows

print(f"\nScraping {len(company_list)} companies (10 threads)...")
done = 0
with ThreadPoolExecutor(max_workers=10) as pool:
    futures = {pool.submit(scrape_company, c): c for c in company_list}
    for f in as_completed(futures):
        cname, cid, err, result_rows = f.result()
        done += 1
        if err:
            errors.append({"company": cname, "id": cid, "error": err})
            print(f"  [{done}/{len(company_list)}] ERROR {cname}: {err}")
        else:
            rows.extend(result_rows)
            if done % 100 == 0 or done == len(company_list):
                print(f"  [{done}/{len(company_list)}] {len(rows)} people so far")

# ── 3. Deduplicate ────────────────────────────────────────────
seen = {}
for r in rows:
    key = (r["company_id"], r["profile_url"])
    if key not in seen:
        seen[key] = r
    else:
        old_score = sum(1 for v in seen[key].values() if v)
        new_score = sum(1 for v in r.values() if v)
        if new_score > old_score:
            seen[key] = r

final = sorted(seen.values(), key=lambda r: (r["company_name"].lower(), r["last_name"].lower()))
unique_cos = len(set(r["company_id"] for r in final))

# ── 4. Write output ──────────────────────────────────────────
FIELDS = ["company_name","first_name","last_name","professional_title","email","phone","company_address","profile_url","company_id"]

csv_path = os.path.join(OUT_DIR, "commonsku_directory_v2.csv")
with open(csv_path, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, FIELDS, extrasaction="ignore")
    w.writeheader()
    w.writerows(final)

jsonl_path = os.path.join(OUT_DIR, "commonsku_directory_v2.jsonl")
with open(jsonl_path, "w", encoding="utf-8") as f:
    for r in final:
        f.write(json.dumps({k: r.get(k,"") for k in FIELDS}) + "\n")

# ── 5. Report ─────────────────────────────────────────────────
print(f"\n{'='*50}")
print(f"DONE")
print(f"{'='*50}")
print(f"Companies in API:   {len(company_list)}")
print(f"Companies scraped:  {unique_cos}")
print(f"People (deduped):   {len(final)}")
print(f"Errors:             {len(errors)}")
print(f"With email:         {sum(1 for r in final if r['email'])}")
print(f"With phone:         {sum(1 for r in final if r['phone'])}")
print(f"With address:       {sum(1 for r in final if r['company_address'])}")
print(f"CSV:  {csv_path}")
print(f"JSONL: {jsonl_path}")
if errors:
    print(f"\nFailed companies:")
    for e in errors:
        print(f"  {e['company']}: {e['error']}")
