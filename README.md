# 📡 CoopRadar v3 — Ontario Co-op & Intern Alerts
**Scans every ~1 minute. Phone notifications. 100% Free. For UWindsor students.**

---

## What It Does
- Monitors **50+ Ontario tech companies** (Shopify, D2L, KOHO, Geotab, Wealthsimple, ecobee, Kinaxis, and many more)
- Searches **Indeed RSS, LinkedIn, Greenhouse ATS, Lever ATS**
- Only shows **co-op / internship** roles in **Ontario, Canada**
- Skips jobs older than **7 days** — no stale postings
- Sends **instant push notifications** to your phone via ntfy.sh
- Runs every **~1 minute** (GitHub Actions loops internally)
- You can add **your own companies** via Google Sheets — no code editing!

---

## Files in This Repo

| File | What it does |
|------|-------------|
| `scraper.py` | Main scanner — all scraping + notifications |
| `.github/workflows/scan.yml` | GitHub Actions — runs every 5 min, loops 5× internally = ~1 min |
| `requirements.txt` | Python packages |
| `seen_jobs.json` | Tracks already-alerted jobs (auto-updated) |
| `companies_template.csv` | Template for your Google Sheet |

---

## Setup Guide (15 minutes, one-time)

### Step 1 — Install ntfy on Your Phone
| Platform | Link |
|----------|------|
| Android  | [Play Store — ntfy](https://play.google.com/store/apps/details?id=io.heckel.ntfy) |
| iPhone   | [App Store — ntfy](https://apps.apple.com/us/app/ntfy/id1625396347) |

1. Open ntfy app
2. Tap **"+"** → Subscribe to topic
3. Enter a unique name like: `coop-ontario-yourfirstname-2025`
4. Tap Subscribe ✅

---

### Step 2 — Create GitHub Repo
1. Go to [github.com](https://github.com) → Sign in (free)
2. Click **"New repository"**
3. Name: `coop-radar` | Set to **Private** | Click Create
4. Upload all files from this ZIP (drag & drop works in GitHub UI)

---

### Step 3 — Add GitHub Secrets
Go to your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Secret Name | Value |
|-------------|-------|
| `NTFY_TOPIC` | Your ntfy topic (e.g. `coop-ontario-yourname-2025`) |
| `GOOGLE_SHEET_ID` | Your Google Sheet ID (optional — see Step 4) |

---

### Step 4 — Google Sheets (Add Your Own Companies!)
This lets you add companies **without editing any code**.

1. Open [this template](https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms/copy) ← copy it to your Drive
   
   Or create a new Google Sheet with these columns:
   ```
   Column A: Company Name     (e.g.  Geotab)
   Column B: ATS Type         (greenhouse / lever / url)
   Column C: Slug or URL      (e.g.  geotab  OR  https://careers.company.com)
   ```
   
   Example rows:
   ```
   Nokia,          url,         https://careers.nokia.com/jobs#cf-lng=en&cf-cty=Canada
   IBM Canada,     url,         https://www.ibm.com/employment/
   Microsoft,      greenhouse,  microsoft
   Stripe,         greenhouse,  stripe
   ```

2. Click **File → Share → Anyone with link (Viewer)**
3. Copy the Sheet ID from the URL:
   `https://docs.google.com/spreadsheets/d/` **`THIS_PART`** `/edit`
4. Add it as `GOOGLE_SHEET_ID` secret in GitHub

---

### Step 5 — Enable GitHub Actions
1. In your repo → **Actions** tab
2. Click **"I understand my workflows, go ahead and enable them"**
3. To test immediately: click **"CoopRadar"** → **"Run workflow"** → **"Run workflow"**
4. Check your phone — you should get a test notification within ~2 minutes!

---

## How the 1-Minute Trick Works

GitHub Actions minimum schedule is 5 minutes. We work around this:

```
GitHub triggers job every 5 min
         ↓
Python script starts
         ↓
Loop 1 (minute 0): scan all sources → notify
Sleep 60 seconds
Loop 2 (minute 1): scan all sources → notify  
Sleep 60 seconds
Loop 3 (minute 2): scan all sources → notify
Sleep 60 seconds
Loop 4 (minute 3): scan all sources → notify
Sleep 60 seconds
Loop 5 (minute 4): scan all sources → notify
         ↓
Job ends → GitHub triggers again in 5 min
```

**Result: You get alerted within ~1 minute of any new posting.**

---

## Customize Keywords

Edit the top of `scraper.py`:

```python
# Add roles you want
COOP_KEYWORDS = [
    "co-op", "intern", "internship", "new grad",
    "your custom keyword here",   # ← add anything
]

# Add cities
ONTARIO_KEYWORDS = [
    "ontario", "toronto", "waterloo", "windsor",
    "your city here",   # ← add more
]

# Change how old jobs can be (days)
MAX_AGE_DAYS = 7   # set to 1 for only today's jobs, 30 for a month
```

---

## Example Notification on Your Phone

```
🚨 Software Developer Co-op — Shopify
🏢 Shopify
📍 Ottawa, ON · Hybrid
📌 Greenhouse
[Apply Now] → opens job posting
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| No notifications | Check ntfy topic name matches exactly in Secret |
| GitHub Actions not running | Actions tab → enable workflows |
| Getting old jobs | Lower `MAX_AGE_DAYS` to 1 or 3 |
| Duplicate alerts | Delete `seen_jobs.json`, commit, re-push |
| Google Sheet not loading | Make sure sharing is set to "Anyone with link" |

---

## Cost: $0/month Forever

| Service | Free Tier |
|---------|-----------|
| GitHub Actions | 2,000 min/month free (you'll use ~1,400) |
| ntfy.sh | Unlimited push notifications |
| Google Sheets | Free |

