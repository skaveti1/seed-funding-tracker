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
AI_KEYWORDS = ["artificial intelligence", " ai ", " ai-", " ai,", " ai."]


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
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
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


def extract_funding_details(text):
    """Extract funding amount, investors, and description from article text."""
    result = {"investors": "", "funding_amount": "", "description": ""}

    # --- Funding amount ---
    # Match patterns like $5 million, $5M, $5,000,000, $5.5 million
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
            if name and name not in investors:
                investors.append(name)
    if investors:
        result["investors"] = "; ".join(investors)

    # --- Description (first 1-2 sentences) ---
    sentences = re.split(r"(?<=[.!?])\s+", text)
    desc_sentences = [s for s in sentences[:5] if len(s) > 30][:2]
    if desc_sentences:
        result["description"] = " ".join(desc_sentences)

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
    if entry.get("_investors"):
        print(f"Investors:   {entry['_investors']}")
    if entry.get("_description"):
        print(f"Description: {entry['_description']}")
    print()


def send_email(articles):
    """Send an email summary of new articles."""
    app_password = os.environ.get("GMAIL_APP_PASSWORD")
    if not app_password:
        print("GMAIL_APP_PASSWORD not set — skipping email.")
        return

    subject = f"AI Seed Funding Alert: {len(articles)} new article(s)"

    rows = ""
    for a in articles:
        rows += f"""
        <tr>
            <td style="padding:8px;border:1px solid #ddd;">
                <a href="{a.get('link', '')}">{a.get('title', '')}</a>
            </td>
            <td style="padding:8px;border:1px solid #ddd;">{a.get('_source', '')}</td>
            <td style="padding:8px;border:1px solid #ddd;">{a.get('_funding_amount', 'N/A')}</td>
            <td style="padding:8px;border:1px solid #ddd;">{a.get('_investors', 'N/A')}</td>
            <td style="padding:8px;border:1px solid #ddd;">{a.get('_description', '')}</td>
        </tr>"""

    html = f"""\
    <html>
    <body>
    <h2>AI Seed Funding Tracker — {len(articles)} New Article(s)</h2>
    <table style="border-collapse:collapse;width:100%;font-family:Arial,sans-serif;">
        <tr style="background:#f4f4f4;">
            <th style="padding:8px;border:1px solid #ddd;">Title</th>
            <th style="padding:8px;border:1px solid #ddd;">Source</th>
            <th style="padding:8px;border:1px solid #ddd;">Amount</th>
            <th style="padding:8px;border:1px solid #ddd;">Investors</th>
            <th style="padding:8px;border:1px solid #ddd;">Description</th>
        </tr>
        {rows}
    </table>
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
                    entry["_funding_amount"] = details["funding_amount"]
                    entry["_investors"] = details["investors"]
                    entry["_description"] = details["description"]
        all_filtered.extend(filtered)

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
            writer.writerow(["Title", "Source", "Link", "Published",
                             "Funding Amount", "Investors", "Description"])
        for article in new_articles:
            writer.writerow([
                article.get("title", ""),
                article.get("_source", ""),
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
