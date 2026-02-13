import csv
import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import feedparser
import requests
from bs4 import BeautifulSoup

SENDER_EMAIL = "skaveti@gmail.com"
RECIPIENT_EMAIL = "shail@thefounder.vc"

FEEDS = [
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/"},
    {"name": "VentureBeat", "url": "https://venturebeat.com/feed/"},
    {"name": "Crunchbase News", "url": "https://news.crunchbase.com/feed/"},
    {"name": "SiliconANGLE", "url": "https://siliconangle.com/feed/"},
    {"name": "GeekWire Startups", "url": "https://www.geekwire.com/startups/feed/"},
    {"name": "The Verge AI", "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"},
    {"name": "Ars Technica AI", "url": "https://arstechnica.com/ai/feed/"},
    {"name": "Wired", "url": "https://www.wired.com/feed/rss"},
]

# Words that indicate seed funding
SEED_KEYWORDS = [
    "seed funding", "seed round", "seed stage", "pre-seed",
    "seed investment", "seed capital", "seed financing",
    "seed money", "seed extension", "seed raise",
    "angel round", "angel funding", "angel investment",
    "early-stage funding", "early stage funding",
    "raises seed", "raised seed", "closes seed", "closed seed",
    "series seed",
]

# Words that indicate AI
AI_KEYWORDS = [
    "artificial intelligence", " ai ", " ai-", " ai,", " ai.",
    "machine learning", "deep learning", "neural network",
    "llm", "large language model", "generative ai", "genai",
    "agentic", "chatbot", "gpt", "claude", "openai", "anthropic",
]


def fetch_feed(url):
    """Download and parse an RSS feed."""
    feed = feedparser.parse(url)
    if feed.bozo and not feed.entries:
        print(f"Error fetching feed: {feed.bozo_exception}")
        return []
    return feed.entries


def matches_keywords(text, keywords):
    """Check if any keyword appears in the text (case-insensitive)."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)


def filter_articles(entries):
    """Return articles that mention both seed funding AND AI."""
    results = []
    for entry in entries:
        title = entry.get("title", "")
        summary = entry.get("summary", "")
        combined = f" {title} {summary} "  # extra spaces help match " ai "

        has_seed = matches_keywords(combined, SEED_KEYWORDS)
        has_ai = matches_keywords(combined, AI_KEYWORDS)

        if has_seed and has_ai:
            results.append(entry)
    return results


def fetch_article_text(url):
    """Fetch an article page and return its plain text content."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  Could not fetch {url}: {e}")
        return ""

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove script/style tags
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()

    # Try common article body selectors
    article = (
        soup.find("article")
        or soup.find("div", class_=re.compile(r"article|post|entry|content", re.I))
        or soup.find("main")
        or soup.body
    )
    if article is None:
        return ""
    return article.get_text(separator=" ", strip=True)


INDUSTRY_KEYWORDS = {
    "AI/ML": ["artificial intelligence", "machine learning", "deep learning", "neural network", "llm", "large language model"],
    "Music": ["music", "audio", "sound", "streaming", "spotify"],
    "Real Estate": ["real estate", "property", "housing", "mortgage", "realty"],
    "Developer Tools": ["developer", "code", "github", "programming", "software development", "devops"],
    "Robotics": ["robot", "humanoid", "automation", "manufacturing"],
    "Healthcare": ["health", "medical", "biotech", "pharma", "clinical"],
    "Fintech": ["fintech", "banking", "payment", "crypto", "blockchain", "financial"],
    "Security": ["security", "cybersecurity", "privacy", "encryption"],
    "Enterprise": ["enterprise", "saas", "b2b", "business software"],
    "Consumer": ["consumer", "retail", "e-commerce", "shopping"],
}

LATER_STAGE_KEYWORDS = ["series a", "series b", "series c", "series d", "series e", "series f", "growth round", "late-stage"]


def detect_industry(text):
    """Detect the industry/sector from article text."""
    text_lower = text.lower()
    for industry, keywords in INDUSTRY_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return industry
    return "Other"


def is_seed_stage(text):
    """Check if the round is seed/pre-seed (not Series A or later)."""
    text_lower = text.lower()
    for kw in LATER_STAGE_KEYWORDS:
        if kw in text_lower:
            return False
    return True


def extract_company_description(text):
    """Extract a clean 1-2 sentence description of what the company does."""
    # Look for patterns that describe the company
    patterns = [
        r"(?:startup|company|firm|platform)\s+(?:that|which)\s+([^.]+\.)",
        r"(?:develops?|builds?|creates?|offers?|provides?)\s+([^.]+\.)",
        r"(?:is\s+(?:a|an)\s+)([^.]+(?:platform|service|solution|tool|software|app)[^.]*\.)",
    ]

    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            desc = match.group(0).strip()
            if 30 < len(desc) < 300:
                return desc

    # Fallback: find sentences mentioning what company does
    sentences = re.split(r"(?<=[.!?])\s+", text)
    for s in sentences[2:10]:  # Skip first couple (usually metadata)
        s = s.strip()
        if 50 < len(s) < 250 and any(word in s.lower() for word in ["develop", "build", "create", "offer", "provide", "platform", "solution", "help"]):
            return s

    # Last fallback: first substantive sentence
    for s in sentences[:8]:
        s = s.strip()
        if 50 < len(s) < 250:
            return s

    return ""


def extract_funding_details(text):
    """Extract funding amount, investors, industry, and description from article text."""
    result = {"investors": "", "funding_amount": "", "description": "", "industry": "", "is_seed": True}

    # --- Funding amount ---
    amount_pattern = (
        r"\$\s?\d[\d,]*\.?\d*\s*(?:million|mln|mil|billion|bln|bil|thousand|[MBKmk])\b"
    )
    amount_match = re.search(amount_pattern, text, re.IGNORECASE)
    if amount_match:
        result["funding_amount"] = amount_match.group(0).strip()

    # --- Investors ---
    investor_patterns = [
        r"led by ([A-Z][\w\s&',]+?)(?:\.|,| and | with )",
        r"backed by ([A-Z][\w\s&',]+?)(?:\.|,| and | with )",
        r"investors? include ([A-Z][\w\s&',]+?)(?:\.|,)",
        r"participation (?:from|by) ([A-Z][\w\s&',]+?)(?:\.|,)",
        r"funding (?:from|by) ([A-Z][\w\s&',]+?)(?:\.|,)",
        r"investment from ([A-Z][\w\s&',]+?)(?:\.|,)",
    ]
    investors = []
    for pat in investor_patterns:
        for m in re.finditer(pat, text):
            name = m.group(1).strip().rstrip(",")
            if name and name not in investors and len(name) < 50:
                investors.append(name)
    if investors:
        result["investors"] = "; ".join(investors)

    # --- Industry ---
    result["industry"] = detect_industry(text)

    # --- Is seed stage? ---
    result["is_seed"] = is_seed_stage(text)

    # --- Clean description ---
    result["description"] = extract_company_description(text)

    return result


def display_article(entry, source_name=""):
    """Print a single article's details."""
    if source_name:
        print(f"Source:      {source_name}")
    print(f"Title:       {entry.get('title', 'N/A')}")
    print(f"Link:        {entry.get('link', 'N/A')}")
    print(f"Published:   {entry.get('published', 'N/A')}")
    if entry.get("_funding_amount"):
        print(f"Amount:      {entry['_funding_amount']}")
    if entry.get("_industry"):
        print(f"Industry:    {entry['_industry']}")
    if entry.get("_investors"):
        print(f"Investors:   {entry['_investors']}")
    if entry.get("_description"):
        print(f"Description: {entry['_description']}")
    print()


def parse_amount_to_number(amount_str):
    """Convert funding amount string to a number for summing."""
    if not amount_str:
        return 0
    amount_str = amount_str.lower().replace(",", "").replace("$", "").strip()
    multiplier = 1
    if "billion" in amount_str or "bln" in amount_str or "bil" in amount_str or amount_str.endswith("b"):
        multiplier = 1_000_000_000
        amount_str = re.sub(r"(billion|bln|bil|b)\b", "", amount_str)
    elif "million" in amount_str or "mln" in amount_str or "mil" in amount_str or amount_str.endswith("m"):
        multiplier = 1_000_000
        amount_str = re.sub(r"(million|mln|mil|m)\b", "", amount_str)
    elif "thousand" in amount_str or amount_str.endswith("k"):
        multiplier = 1_000
        amount_str = re.sub(r"(thousand|k)\b", "", amount_str)
    try:
        return float(amount_str.strip()) * multiplier
    except ValueError:
        return 0


def format_total_amount(total):
    """Format a total amount nicely."""
    if total >= 1_000_000_000:
        return f"${total / 1_000_000_000:.1f}B"
    elif total >= 1_000_000:
        return f"${total / 1_000_000:.1f}M"
    elif total >= 1_000:
        return f"${total / 1_000:.1f}K"
    else:
        return f"${total:.0f}"


def get_top_investors(articles, limit=5):
    """Get the most frequently mentioned investors."""
    investor_counts = {}
    for a in articles:
        investors = a.get("_investors", "")
        if investors:
            for inv in investors.split(";"):
                inv = inv.strip()
                if inv and len(inv) < 50:
                    investor_counts[inv] = investor_counts.get(inv, 0) + 1
    sorted_investors = sorted(investor_counts.items(), key=lambda x: x[1], reverse=True)
    return sorted_investors[:limit]


def send_email(articles):
    """Send an email summary of new articles."""
    app_password = os.environ.get("GMAIL_APP_PASSWORD")
    if not app_password:
        print("GMAIL_APP_PASSWORD not set — skipping email.")
        return

    # Calculate summary stats
    total_deals = len(articles)
    total_funding = sum(parse_amount_to_number(a.get("_funding_amount", "")) for a in articles)
    top_investors = get_top_investors(articles)

    subject = f"AI Seed Funding Alert: {total_deals} new deal(s) - {format_total_amount(total_funding)} total"

    # Build investor list for summary
    investor_html = ""
    if top_investors:
        investor_items = [f"<li>{inv} ({count} deal{'s' if count > 1 else ''})</li>" for inv, count in top_investors]
        investor_html = f"<ul style='margin:5px 0;padding-left:20px;'>{''.join(investor_items)}</ul>"
    else:
        investor_html = "<p style='margin:5px 0;color:#666;'>No investor data available</p>"

    rows = ""
    for a in articles:
        desc = a.get('_description', '') or 'N/A'
        if len(desc) > 200:
            desc = desc[:200] + "..."
        rows += f"""
        <tr>
            <td style="padding:12px;border:1px solid #e0e0e0;vertical-align:top;">
                <a href="{a.get('link', '')}" style="color:#1a73e8;text-decoration:none;font-weight:500;">{a.get('title', '')}</a>
            </td>
            <td style="padding:12px;border:1px solid #e0e0e0;vertical-align:top;">{a.get('_source', '')}</td>
            <td style="padding:12px;border:1px solid #e0e0e0;vertical-align:top;">{a.get('_industry', 'N/A')}</td>
            <td style="padding:12px;border:1px solid #e0e0e0;vertical-align:top;font-weight:600;color:#2e7d32;">{a.get('_funding_amount', 'N/A')}</td>
            <td style="padding:12px;border:1px solid #e0e0e0;vertical-align:top;">{a.get('_investors', 'N/A')}</td>
            <td style="padding:12px;border:1px solid #e0e0e0;vertical-align:top;font-size:13px;color:#555;">{desc}</td>
        </tr>"""

    html = f"""\
    <html>
    <body style="font-family:Arial,sans-serif;max-width:1200px;margin:0 auto;padding:20px;">
    <h2 style="color:#1a1a1a;border-bottom:2px solid #1a73e8;padding-bottom:10px;">
        AI Seed Funding Tracker
    </h2>

    <div style="background:#f8f9fa;border-radius:8px;padding:20px;margin-bottom:20px;">
        <h3 style="margin-top:0;color:#333;">Summary</h3>
        <table style="width:100%;border-collapse:collapse;">
            <tr>
                <td style="padding:8px 0;width:33%;"><strong>Total Deals:</strong> {total_deals}</td>
                <td style="padding:8px 0;width:33%;"><strong>Total Funding:</strong> {format_total_amount(total_funding)}</td>
            </tr>
        </table>
        <div style="margin-top:10px;">
            <strong>Top Investors:</strong>
            {investor_html}
        </div>
    </div>

    <table style="border-collapse:collapse;width:100%;font-size:14px;">
        <tr style="background:#1a73e8;color:white;">
            <th style="padding:12px;border:1px solid #1a73e8;text-align:left;">Title</th>
            <th style="padding:12px;border:1px solid #1a73e8;text-align:left;">Source</th>
            <th style="padding:12px;border:1px solid #1a73e8;text-align:left;">Industry</th>
            <th style="padding:12px;border:1px solid #1a73e8;text-align:left;">Amount</th>
            <th style="padding:12px;border:1px solid #1a73e8;text-align:left;">Investors</th>
            <th style="padding:12px;border:1px solid #1a73e8;text-align:left;">Description</th>
        </tr>
        {rows}
    </table>

    <p style="margin-top:20px;font-size:12px;color:#666;">
        Generated by AI Seed Funding Tracker
    </p>
    </body>
    </html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECIPIENT_EMAIL
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, app_password)
            server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
        print(f"Email sent to {RECIPIENT_EMAIL}")
    except Exception as e:
        print(f"Failed to send email: {e}")


def main():
    all_filtered = []

    for feed in FEEDS:
        print(f"Fetching {feed['name']} RSS feed...")
        entries = fetch_feed(feed["url"])

        if not entries:
            print(f"  No entries found in {feed['name']} feed.\n")
            continue

        print(f"  Total articles in feed: {len(entries)}")
        filtered = filter_articles(entries)
        print(f"  Articles about AI + seed funding: {len(filtered)}\n")

        for entry in filtered:
            entry["_source"] = feed["name"]
            url = entry.get("link", "")
            if url:
                print(f"  Fetching details: {entry.get('title', '')[:60]}...")
                text = fetch_article_text(url)
                if text:
                    details = extract_funding_details(text)
                    if not details["is_seed"]:
                        print(f"    Skipping (not seed/pre-seed round)")
                        continue
                    entry["_funding_amount"] = details["funding_amount"]
                    entry["_investors"] = details["investors"]
                    entry["_description"] = details["description"]
                    entry["_industry"] = details["industry"]
                else:
                    # Fallback: include article even if scraping failed
                    print(f"    Could not scrape, using fallback")
                    entry["_funding_amount"] = ""
                    entry["_investors"] = ""
                    # Clean HTML from summary
                    summary = entry.get("summary", "")
                    summary = re.sub(r"<[^>]+>", "", summary).strip()[:200]
                    entry["_description"] = summary
                    entry["_industry"] = detect_industry(entry.get("title", "") + " " + entry.get("summary", ""))
                all_filtered.append(entry)

    if not all_filtered:
        print("No matching articles right now. Try again later!")
        return

    print("-" * 60)
    for article in all_filtered:
        display_article(article, source_name=article.get("_source", ""))

    filename = "results.csv"
    file_exists = os.path.isfile(filename)
    existing_links = set()
    if file_exists:
        with open(filename, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_links.add(row.get("Link", ""))

    new_articles = [a for a in all_filtered if a.get("link", "") not in existing_links]

    if not new_articles:
        print("No new articles to add (all duplicates).")
        return

    with open(filename, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Title", "Source", "Industry", "Link", "Published",
                             "Funding Amount", "Investors", "Description"])
        for article in new_articles:
            writer.writerow([
                article.get("title", ""),
                article.get("_source", ""),
                article.get("_industry", ""),
                article.get("link", ""),
                article.get("published", ""),
                article.get("_funding_amount", ""),
                article.get("_investors", ""),
                article.get("_description", ""),
            ])
    print(f"{len(new_articles)} new result(s) appended to {filename}")

    send_email(new_articles)


if __name__ == "__main__":
    main()
