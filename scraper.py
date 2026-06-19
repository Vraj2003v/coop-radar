"""
CoopRadar v4 - Ontario Co-op/Intern Alert System
=================================================
MODIFIED: STRICT Winter 2027 / January 2027 ONLY
- Only alerts on postings explicitly mentioning Winter 2027 or Jan 2027
- No generic "intern" / "co-op" noise from other terms/years
- 150+ Ontario companies monitored
- Greenhouse, Lever, Workday, Indeed RSS, LinkedIn
- Push notifications via ntfy.sh (free)
- Loops every 1 min inside GitHub Actions
"""

import requests, json, hashlib, os, time, xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed

# ═══════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════
NTFY_TOPIC       = os.environ.get("NTFY_TOPIC", "coop-alerts-uwindsor-change-this")
NTFY_SERVER      = "https://ntfy.sh"
GOOGLE_SHEET_ID  = os.environ.get("GOOGLE_SHEET_ID", "")
MAX_AGE_DAYS     = 90
SEEN_FILE        = "seen_jobs.json"
LOOP_MINUTES     = 5
MAX_WORKERS      = 10

# ═══════════════════════════════════════════════════════════
# STRICT WINTER 2027 KEYWORDS — title must contain at least ONE
# No generic "co-op" / "intern" alone — must be year-specific
# ═══════════════════════════════════════════════════════════
COOP_KEYWORDS = [
    # ── Hard year/term markers — Winter 2027 ─────────────────
    "winter 2027",
    "january 2027",
    "jan 2027",
    "jan2027",
    "w2027",
    "w27",
    "winter27",
    "february 2027",
    "feb 2027",
    "feb2027",

    # ── Spring 2027 (some schools call Jan start "Spring") ───
    "spring 2027",
    "spring2027",

    # ── Generic winter term — safe because "winter" alone
    #    almost always means the Jan intake in Canadian postings
    "winter co-op",
    "winter intern",
    "winter coop",
    "winter work term",
    "winter term",
    "winter placement",
    "winter student",
]

# ── Broad generic keywords used ONLY for Greenhouse/Lever/Workday
#    company board scraping (where we can't embed a year in the URL).
#    These are intentionally wider so we don't miss a posting that
#    says "Co-op Student – Winter 2027" — the year check below
#    confirms the posting before alerting.
GENERIC_BOARD_KEYWORDS = [
    "co-op", "coop", "co op", "intern", "internship",
    "work term", "work-term", "student placement",
    "student position", "student developer",
    "pey", "pey co-op",
]

# A second-pass filter: if a board job matched a generic keyword,
# it MUST also contain at least one of these to get an alert.
YEAR_CONFIRM_KEYWORDS = [
    "winter 2027", "january 2027", "jan 2027", "jan2027",
    "w2027", "w27", "winter27",
    "february 2027", "feb 2027",
    "spring 2027", "spring2027",
    "winter co-op", "winter intern", "winter coop",
    "winter work term", "winter term", "winter placement",
    "winter student",
]

ONTARIO_KEYWORDS = [
    "ontario","toronto","ottawa","waterloo","kitchener","windsor",
    "london","hamilton","mississauga","brampton","markham","vaughan",
    "north york","scarborough","etobicoke","burlington","oakville",
    "cambridge","guelph","oshawa","ajax","pickering","aurora","barrie",
    "kanata","nepean","richmond hill","thornhill","newmarket",
    " on,","on canada"," on "," ontario","greater toronto",
    "gta","remote","hybrid",
]

HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-CA,en;q=0.9",
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
}

# ═══════════════════════════════════════════════════════════
# GREENHOUSE ATS
# ═══════════════════════════════════════════════════════════
GREENHOUSE_COMPANIES = {
    "shopify":"Shopify","d2l":"D2L (Desire2Learn)","wealthsimple":"Wealthsimple",
    "hootsuite":"Hootsuite","lightspeed":"Lightspeed Commerce","coveo":"Coveo",
    "cohere":"Cohere AI","1password":"1Password","assent":"Assent Compliance",
    "ecobee":"ecobee","kinaxis":"Kinaxis","magnet":"Magnet Forensics",
    "fullscript":"Fullscript","tucows":"Tucows","resolver":"Resolver",
    "loopio":"Loopio","crowdriff":"CrowdRiff","myplanet":"Myplanet",
    "solink":"Solink","miovision":"Miovision","intelex":"Intelex Technologies",
    "martello":"Martello Technologies","fellow":"Fellow.app","relay":"Relay Financial",
    "benchling":"Benchling","absorblms":"Absorb LMS","clearco":"Clearco",
    "ritual":"Ritual","ubisoft":"Ubisoft","nuvei":"Nuvei",
    "vendasta":"Vendasta","benevity":"Benevity","partnerstack":"PartnerStack",
    "dialogue":"Dialogue Health","inkblot":"Inkblot Therapy","league":"League Health",
    "wattpad":"Wattpad","freshbooks":"FreshBooks","wavefinancial":"Wave Financial",
    "klue":"Klue","certn":"Certn","coconutsoftware":"Coconut Software",
    "snapcommerce":"Snapcommerce","drop":"Drop Technologies","financeit":"Financeit",
    "nudge":"Nudge","pivotal":"Pivotal Canada","kognitive":"Kognitive Networks",
    "macadamian":"Macadamian Technologies","distributive":"Distributive",
    "cifinancial":"CI Financial","manuliferecruiting":"Manulife",
    "sunlife":"Sun Life Financial","intactfc":"Intact Financial",
    "equalizer":"EQ Bank (Equitable Bank)","borrowell":"Borrowell",
    "nesto":"nesto","properly":"Properly","hardbacon":"Hardbacon",
    "mylo":"Mylo Financial","tulip-retail":"Tulip Retail",
    "opentext":"OpenText","descartes":"Descartes Systems","ptc":"PTC",
    "maplesoft":"Maplesoft","intelliware":"Intelliware","aislelabs":"Aislelabs",
    "vertafore":"Vertafore","zynga":"Zynga Toronto","uken":"Uken Games",
    "caseware":"CaseWare","tempoplatform":"Tempo Platform","tulip":"Tulip",
    "procurify":"Procurify","proposify":"Proposify","validere":"Validere",
    "vena":"Vena Solutions","klipfolio":"Klipfolio","genesys":"Genesys",
    "cybereason":"Cybereason","darktrace":"Darktrace","forescout":"Forescout Technologies",
    "securityscorecard":"SecurityScorecard","beyondtrust":"BeyondTrust","irdeto":"Irdeto",
    "ciena":"Ciena","ribbon":"Ribbon Communications","ericsson":"Ericsson Canada",
    "pointclickcare":"PointClickCare","telmediq":"TelmedIQ","maple":"Maple Health",
    "greenspace":"Greenspace Mental Health","pillway":"Pillway",
    "songkick":"Songkick","verticalscope":"VerticalScope",
}

# ═══════════════════════════════════════════════════════════
# LEVER ATS
# ═══════════════════════════════════════════════════════════
LEVER_COMPANIES = {
    "koho":"KOHO Financial","geotab":"Geotab","vehikl":"Vehikl",
    "pelmorex":"Pelmorex / The Weather Network","brock-solutions":"Brock Solutions",
    "distributive":"Distributive","nudgesecurity":"Nudge Security",
    "magnetforensics":"Magnet Forensics","proofpoint":"Proofpoint",
    "arcticwolf":"Arctic Wolf Networks","xanadu":"Xanadu Quantum",
    "wealthsimple":"Wealthsimple (Lever)","mogo":"Mogo Financial",
    "payfare":"Payfare","financeit":"Financeit","clearbanc":"Clearco / Clearbanc",
    "paladin":"Paladin Cyber",
}

# ═══════════════════════════════════════════════════════════
# WORKDAY / CUSTOM CAREER PAGES
# ═══════════════════════════════════════════════════════════
WORKDAY_COMPANIES = {
    "RBC":            "https://jobs.rbc.com/ca/en/search-results?keywords=co-op+intern&country=Canada",
    "TD Bank":        "https://jobs.td.com/en-CA/job-search-results/?keyword=co-op+intern",
    "BMO":            "https://bmo.wd3.myworkdayjobs.com/en-US/Privileged/jobs?q=co-op+intern",
    "Scotiabank":     "https://jobs.scotiabank.com/search/?q=co-op+intern&l=Ontario",
    "CIBC":           "https://cibc.wd3.myworkdayjobs.com/en-US/campus/jobs?q=co-op+intern",
    "Manulife":       "https://manulife.wd3.myworkdayjobs.com/en-US/MFCJH_Careers/jobs?q=co-op+intern",
    "Sun Life":       "https://sunlife.wd3.myworkdayjobs.com/en-US/Experienced-EN/jobs?q=co-op+intern",
    "Intact":         "https://careers.intactfc.com/ca/en/search-results?keywords=intern+co-op",
    "CI Financial":   "https://careers.cifinancial.com/en/search-results?keywords=intern+co-op",
    "Ceridian/Dayforce":"https://dayforce.wd1.myworkdayjobs.com/en-US/Dayforce/jobs?q=intern+co-op",
    "OpenText":       "https://opentext.wd1.myworkdayjobs.com/en-US/careers/jobs?q=co-op+intern",
    "Autodesk":       "https://autodesk.wd1.myworkdayjobs.com/en-US/Ext/jobs?q=intern",
    "Motorola":       "https://motorolasolutions.wd5.myworkdayjobs.com/en-US/Careers/jobs?q=co-op+intern",
    "Nokia":          "https://fa-evmr-saasfaprod1.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/jobs?keyword=co-op+intern",
    "Citi Canada":    "https://citi.wd5.myworkdayjobs.com/en-US/Citi_Early_Careers_Events_Site/jobs?q=intern",
    "KPMG Canada":    "https://jobs.kpmg.ca/ca/en/search-results?keywords=co-op+intern",
    "Deloitte Canada":"https://careers.deloitte.ca/ca/en/search-results?keywords=co-op+intern",
    "PwC Canada":     "https://pwc.wd3.myworkdayjobs.com/en-US/Global_Campus_Careers/jobs?q=co-op",
    "IBM Canada":     "https://careers.ibm.com/jobs?shiftby=25&limit=25&start=0&keyword=co-op+intern&country=CA",
    "Amazon Canada":  "https://www.amazon.jobs/en/search?base_query=intern+co-op&loc_query=Ontario%2C+Canada",
    "Microsoft CA":   "https://jobs.careers.microsoft.com/global/en/search?q=intern+co-op&lc=Ontario%2C+Canada",
    "Google Canada":  "https://careers.google.com/jobs/results/?q=intern+co-op&location=Ontario%2C+Canada",
    "BlackBerry QNX": "https://bb.wd3.myworkdayjobs.com/en-US/Student_BlackBerry/jobs?q=co-op+intern",
    "Rogers":         "https://jobs.rogers.com/search/?q=intern+co-op&l=Ontario",
    "Bell Canada":    "https://jobs.bell.ca/ca/en/search-results?keywords=intern+co-op",
    "TELUS":          "https://careers.telus.com/search/?q=intern+co-op&l=Ontario",
    "SAP Canada":     "https://jobs.sap.com/search/?q=intern+co-op&location=Ontario%2C+Canada",
    "Loblaw":         "https://myview.wd3.myworkdayjobs.com/en-US/loblaw_careers_entry/jobs?q=intern+co-op",
    "Lumentum":       "https://lumentum.wd5.myworkdayjobs.com/en-US/LITE/jobs?q=co-op+intern",
    "Mitel":          "https://mitel.wd1.myworkdayjobs.com/en-US/MitelExternal/jobs?q=co-op+intern",
}

# ═══════════════════════════════════════════════════════════
# INDEED RSS — Winter 2027 / Jan 2027 ONLY in every query
# ═══════════════════════════════════════════════════════════
INDEED_RSS_SEARCHES = [
    ("Winter 2027 Co-op Ontario",
     "https://ca.indeed.com/rss?q=%22winter+2027%22+co-op&l=Ontario&sort=date&fromage=90"),
    ("Winter 2027 Intern Ontario",
     "https://ca.indeed.com/rss?q=%22winter+2027%22+intern&l=Ontario&sort=date&fromage=90"),
    ("January 2027 Co-op Ontario",
     "https://ca.indeed.com/rss?q=%22january+2027%22+co-op&l=Ontario&sort=date&fromage=90"),
    ("January 2027 Intern Ontario",
     "https://ca.indeed.com/rss?q=%22january+2027%22+intern&l=Ontario&sort=date&fromage=90"),
    ("Jan 2027 Co-op Ontario",
     "https://ca.indeed.com/rss?q=%22jan+2027%22+co-op+intern&l=Ontario&sort=date&fromage=90"),
    ("Spring 2027 Co-op Ontario",
     "https://ca.indeed.com/rss?q=%22spring+2027%22+co-op+intern&l=Ontario&sort=date&fromage=90"),
    ("Winter 2027 SWE Ontario",
     "https://ca.indeed.com/rss?q=%22winter+2027%22+software+developer&l=Ontario&sort=date&fromage=90"),
    ("Winter 2027 Developer Ontario",
     "https://ca.indeed.com/rss?q=%22winter+2027%22+developer&l=Ontario&sort=date&fromage=90"),
    ("Winter 2027 Analyst Ontario",
     "https://ca.indeed.com/rss?q=%22winter+2027%22+analyst&l=Ontario&sort=date&fromage=90"),
    ("Winter 2027 Toronto",
     "https://ca.indeed.com/rss?q=%22winter+2027%22+co-op&l=Toronto%2C+Ontario&sort=date&fromage=90"),
    ("Winter 2027 Waterloo",
     "https://ca.indeed.com/rss?q=%22winter+2027%22+co-op&l=Waterloo%2C+Ontario&sort=date&fromage=90"),
    ("Winter 2027 Ottawa",
     "https://ca.indeed.com/rss?q=%22winter+2027%22+co-op&l=Ottawa%2C+Ontario&sort=date&fromage=90"),
    ("Winter term co-op Ontario",
     "https://ca.indeed.com/rss?q=%22winter+term%22+co-op+2027&l=Ontario&sort=date&fromage=90"),
    ("Winter work term Ontario",
     "https://ca.indeed.com/rss?q=%22winter+work+term%22+2027&l=Ontario&sort=date&fromage=90"),
]

# ═══════════════════════════════════════════════════════════
# LINKEDIN — Winter 2027 / Jan 2027 ONLY in every query
# ═══════════════════════════════════════════════════════════
LINKEDIN_SEARCHES = [
    ("LinkedIn: Winter 2027 Co-op Ontario",
     "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
     "?keywords=%22winter+2027%22+co-op&location=Ontario%2C+Canada&sortBy=DD&start=0"),
    ("LinkedIn: Winter 2027 Intern Ontario",
     "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
     "?keywords=%22winter+2027%22+intern&location=Ontario%2C+Canada&sortBy=DD&start=0"),
    ("LinkedIn: January 2027 Co-op Ontario",
     "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
     "?keywords=%22january+2027%22+co-op&location=Ontario%2C+Canada&sortBy=DD&start=0"),
    ("LinkedIn: January 2027 Intern Ontario",
     "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
     "?keywords=%22january+2027%22+intern&location=Ontario%2C+Canada&sortBy=DD&start=0"),
    ("LinkedIn: Spring 2027 Co-op Ontario",
     "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
     "?keywords=%22spring+2027%22+co-op+intern&location=Ontario%2C+Canada&sortBy=DD&start=0"),
    ("LinkedIn: Winter 2027 SWE Ontario",
     "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
     "?keywords=%22winter+2027%22+software+developer&location=Ontario%2C+Canada&sortBy=DD&start=0"),
    ("LinkedIn: Winter 2027 Developer Ontario",
     "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
     "?keywords=%22winter+2027%22+developer&location=Ontario%2C+Canada&sortBy=DD&start=0"),
    ("LinkedIn: Winter term co-op Ontario",
     "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
     "?keywords=%22winter+term%22+co-op+2027&location=Ontario%2C+Canada&sortBy=DD&start=0"),
]

# ═══════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════
def job_id(title, company, url=""):
    raw = f"{title.lower().strip()}|{company.lower().strip()}|{url.split('?')[0]}"
    return hashlib.md5(raw.encode()).hexdigest()

def is_winter2027(title):
    """Strict check — title must contain a Winter 2027 / Jan 2027 marker."""
    t = title.lower()
    return any(kw in t for kw in COOP_KEYWORDS)

def is_board_job(title):
    """First pass for company board scraping — generic co-op/intern match."""
    t = title.lower()
    return any(kw in t for kw in GENERIC_BOARD_KEYWORDS)

def is_year_confirmed(title):
    """Second pass — confirms board job is actually Winter 2027."""
    t = title.lower()
    return any(kw in t for kw in YEAR_CONFIRM_KEYWORDS)

def is_ontario(location):
    if not location: return True
    loc = location.lower()
    return any(kw in loc for kw in ONTARIO_KEYWORDS)

def is_recent(pub_date_str):
    if not pub_date_str: return True
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(pub_date_str)
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).days <= MAX_AGE_DAYS
    except Exception:
        return True

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f: return set(json.load(f))
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f: json.dump(sorted(list(seen)), f, indent=2)

def notify(title, company, location, url, source):
    clean_title = " ".join(title.split())[:60]
    clean_loc   = " ".join((location or "Ontario, Canada").split())
    clean_url   = (url or "").split()[0] if url else ""
    ascii_title = clean_title.encode("ascii", errors="ignore").decode("ascii").strip()
    if not ascii_title: ascii_title = "New Winter 2027 Co-op Posted"
    msg = (
        f"Position: {clean_title}\n"
        f"Company: {company}\n"
        f"Location: {clean_loc}\n"
        f"Source: {source}"
    )
    try:
        r = requests.post(
            f"{NTFY_SERVER}/{NTFY_TOPIC}",
            data=msg.encode("utf-8"),
            headers={
                "Title":        ascii_title,
                "Priority":     "high",
                "Tags":         "briefcase,maple_leaf,snowflake",
                "Click":        clean_url,
                "Actions":      f"view, Apply Now, {clean_url}, clear=true",
                "Content-Type": "text/plain; charset=utf-8",
            }, timeout=10)
        ok = "+" if r.status_code == 200 else f"? {r.status_code}"
        print(f"  [{ok}] [{company}] {clean_title[:50]}")
    except Exception as e:
        print(f"  [ERR] notify: {e}")

# ═══════════════════════════════════════════════════════════
# SCRAPERS
# ═══════════════════════════════════════════════════════════
def scrape_greenhouse(slug, company_name, seen, lock):
    new_jobs = []
    try:
        r = requests.get(
            f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true",
            headers=HEADERS, timeout=12)
        if r.status_code != 200: return []
        for job in r.json().get("jobs", []):
            title    = job.get("title", "")
            location = job.get("location", {}).get("name", "")
            job_url  = job.get("absolute_url", "")
            # Two-pass: generic board match + year confirmation
            if not is_board_job(title): continue
            if not is_year_confirmed(title): continue
            if not is_ontario(location): continue
            jid = job_id(title, company_name, job_url)
            with lock:
                if jid not in seen:
                    new_jobs.append({"id":jid,"title":title,"company":company_name,
                                     "location":location,"url":job_url,"source":"Greenhouse"})
                    seen.add(jid)
    except Exception:
        pass
    return new_jobs

def scrape_lever(slug, company_name, seen, lock):
    new_jobs = []
    try:
        r = requests.get(
            f"https://api.lever.co/v0/postings/{slug}?mode=json",
            headers=HEADERS, timeout=12)
        if r.status_code != 200: return []
        for job in r.json():
            title    = job.get("text", "")
            location = job.get("categories", {}).get("location", "")
            job_url  = job.get("hostedUrl", "")
            created  = job.get("createdAt", 0)
            if not is_board_job(title): continue
            if not is_year_confirmed(title): continue
            if not is_ontario(location): continue
            if created:
                age_days = (time.time() - created/1000) / 86400
                if age_days > MAX_AGE_DAYS: continue
            jid = job_id(title, company_name, job_url)
            with lock:
                if jid not in seen:
                    new_jobs.append({"id":jid,"title":title,"company":company_name,
                                     "location":location,"url":job_url,"source":"Lever"})
                    seen.add(jid)
    except Exception:
        pass
    return new_jobs

def scrape_indeed_rss(label, rss_url, seen, lock):
    new_jobs = []
    try:
        r = requests.get(rss_url, headers=HEADERS, timeout=15)
        if r.status_code != 200: return []
        root    = ET.fromstring(r.content)
        channel = root.find("channel")
        if not channel: return []
        for item in channel.findall("item"):
            raw  = (item.findtext("title") or "").strip()
            url  = (item.findtext("link")  or "").strip()
            pub  = (item.findtext("pubDate") or "").strip()
            if not is_recent(pub): continue
            parts    = [p.strip() for p in raw.split(" - ")]
            title    = parts[0] if parts else raw
            company  = parts[1] if len(parts) >= 2 else "Unknown"
            location = parts[2] if len(parts) >= 3 else "Ontario, Canada"
            # Indeed RSS already has "winter 2027" baked into the query URL,
            # but double-check the title to avoid stray results
            if not is_winter2027(title): continue
            if not is_ontario(location): continue
            jid = job_id(title, company, url)
            with lock:
                if jid not in seen:
                    new_jobs.append({"id":jid,"title":title,"company":company,
                                     "location":location,"url":url,"source":"Indeed"})
                    seen.add(jid)
    except Exception:
        pass
    return new_jobs

def scrape_linkedin(label, url, seen, lock):
    new_jobs = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200: return []
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.find_all("li"):
            title_el   = card.find("h3", class_=lambda c: c and "base-search-card__title" in str(c))
            company_el = card.find("h4", class_=lambda c: c and "base-search-card__subtitle" in str(c))
            loc_el     = card.find("span", class_=lambda c: c and "job-search-card__location" in str(c))
            link_el    = card.find("a", href=True)
            time_el    = card.find("time")
            if not title_el: continue
            title    = title_el.get_text(strip=True)
            company  = company_el.get_text(strip=True) if company_el else "Unknown"
            location = loc_el.get_text(strip=True) if loc_el else ""
            job_url  = link_el["href"].split("?")[0] if link_el else ""
            if time_el and time_el.get("datetime"):
                try:
                    dt = datetime.fromisoformat(time_el["datetime"].replace("Z","+00:00"))
                    if (datetime.now(timezone.utc) - dt).days > MAX_AGE_DAYS: continue
                except Exception: pass
            if not is_winter2027(title): continue
            if not is_ontario(location): continue
            jid = job_id(title, company, job_url)
            with lock:
                if jid not in seen:
                    new_jobs.append({"id":jid,"title":title,"company":company,
                                     "location":location,"url":job_url,"source":"LinkedIn"})
                    seen.add(jid)
    except Exception:
        pass
    return new_jobs

def scrape_workday_page(company_name, url, seen, lock):
    new_jobs = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200: return []
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            title = a.get_text(strip=True)
            href  = a["href"]
            if not href.startswith("http"): href = urljoin(url, href)
            if not title or len(title) < 8 or len(title) > 160: continue
            if not is_board_job(title): continue
            if not is_year_confirmed(title): continue
            jid = job_id(title, company_name, href)
            with lock:
                if jid not in seen:
                    new_jobs.append({"id":jid,"title":title,"company":company_name,
                                     "location":"Ontario, Canada","url":href,"source":"Company Site"})
                    seen.add(jid)
    except Exception:
        pass
    return new_jobs

# ═══════════════════════════════════════════════════════════
# GOOGLE SHEET loader
# ═══════════════════════════════════════════════════════════
def load_google_sheet():
    if not GOOGLE_SHEET_ID:
        return {}, {}, {}
    gh_extra, lv_extra, url_extra = {}, {}, {}
    try:
        csv_url = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/export?format=csv&gid=0"
        r = requests.get(csv_url, timeout=10)
        if r.status_code != 200: return gh_extra, lv_extra, url_extra
        for line in r.text.strip().splitlines()[1:]:
            parts = [p.strip().strip('"') for p in line.split(",")]
            if len(parts) < 3: continue
            name, ats, slug = parts[0], parts[1].lower(), parts[2]
            if not name or not slug: continue
            if ats == "greenhouse": gh_extra[slug] = name
            elif ats == "lever":    lv_extra[slug] = name
            elif ats == "url":      url_extra[name] = slug
        total = len(gh_extra)+len(lv_extra)+len(url_extra)
        if total: print(f"  📊 Google Sheet: +{total} companies loaded")
    except Exception as e:
        print(f"  ⚠️  Google Sheet: {e}")
    return gh_extra, lv_extra, url_extra

# ═══════════════════════════════════════════════════════════
# CONCURRENT SCAN
# ═══════════════════════════════════════════════════════════
def run_scan(seen):
    import threading
    lock    = threading.Lock()
    all_new = []

    gh_extra, lv_extra, url_extra = load_google_sheet()
    all_gh = {**GREENHOUSE_COMPANIES, **gh_extra}
    all_lv = {**LEVER_COMPANIES,      **lv_extra}
    all_wd = {**WORKDAY_COMPANIES,    **url_extra}

    tasks = []
    for slug, name in all_gh.items(): tasks.append(("greenhouse", slug, name))
    for slug, name in all_lv.items(): tasks.append(("lever",      slug, name))
    for label, url  in INDEED_RSS_SEARCHES: tasks.append(("indeed",  label, url))
    for label, url  in LINKEDIN_SEARCHES:   tasks.append(("linkedin",label, url))
    for name,  url  in all_wd.items():      tasks.append(("workday", name,  url))

    print(f"  🚀 Running {len(tasks)} tasks with {MAX_WORKERS} concurrent workers...")

    def run_task(task):
        kind = task[0]
        try:
            if   kind == "greenhouse": return scrape_greenhouse(task[1], task[2], seen, lock)
            elif kind == "lever":      return scrape_lever(task[1], task[2], seen, lock)
            elif kind == "indeed":     return scrape_indeed_rss(task[1], task[2], seen, lock)
            elif kind == "linkedin":   return scrape_linkedin(task[1], task[2], seen, lock)
            elif kind == "workday":    return scrape_workday_page(task[1], task[2], seen, lock)
        except Exception:
            return []
        return []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(run_task, t): t for t in tasks}
        for future in as_completed(futures):
            result = future.result() or []
            all_new.extend(result)
            if result:
                t    = futures[future]
                name = t[2] if len(t) > 2 else t[1]
                print(f"  ✅ {name}: {len(result)} new")

    return all_new

# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════
def main():
    gh_count  = len(GREENHOUSE_COMPANIES)
    lv_count  = len(LEVER_COMPANIES)
    wd_count  = len(WORKDAY_COMPANIES)
    rss_count = len(INDEED_RSS_SEARCHES)
    li_count  = len(LINKEDIN_SEARCHES)
    total_co  = gh_count + lv_count + wd_count

    print(f"\n{'═'*62}")
    print(f"  ❄️  CoopRadar — STRICT Winter 2027 / Jan 2027 ONLY")
    print(f"  📡 ntfy        : {NTFY_TOPIC}")
    print(f"  🏢 Companies   : {total_co} ({gh_count} GH + {lv_count} Lever + {wd_count} Workday)")
    print(f"  🔍 Indeed RSS  : {rss_count} searches | LinkedIn: {li_count} searches")
    print(f"  📅 Filter      : ONLY postings with 'Winter 2027' / 'Jan 2027' in title")
    print(f"  🔁 Loops       : {LOOP_MINUTES} × ~60s | Age limit: {MAX_AGE_DAYS} days")
    print(f"{'═'*62}")

    for cycle in range(LOOP_MINUTES):
        cycle_start = datetime.now(timezone.utc)
        print(f"\n{'─'*62}")
        print(f"  🔄 Cycle {cycle+1}/{LOOP_MINUTES} — {cycle_start.strftime('%H:%M:%S UTC')}")
        print(f"{'─'*62}")

        seen    = load_seen()
        all_new = run_scan(seen)

        print(f"\n  📊 Cycle {cycle+1}: {len(all_new)} new Winter 2027 jobs found")
        if all_new:
            print(f"  📱 Sending {len(all_new)} notification(s)...")
            for job in all_new:
                notify(job["title"], job["company"], job["location"],
                       job["url"], job["source"])
                time.sleep(0.15)
            save_seen(seen)

        if cycle < LOOP_MINUTES - 1:
            elapsed   = (datetime.now(timezone.utc) - cycle_start).seconds
            sleep_for = max(0, 57 - elapsed)
            print(f"\n  ⏳ Next cycle in {sleep_for}s...")
            time.sleep(sleep_for)

    total = len(load_seen())
    print(f"\n✅ All {LOOP_MINUTES} cycles done. Total jobs tracked: {total}")
    print(f"{'═'*62}\n")

if __name__ == "__main__":
    main()
