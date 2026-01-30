import feedparser

FEEDS = [
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/"},
    {"name": "VentureBeat", "url": "https://venturebeat.com/feed/"},
]

# Words that indicate seed funding
SEED_KEYWORDS = ["seed funding", "seed round", "seed stage", "pre-seed"]

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


def display_article(entry, source_name=""):
    """Print a single article's details."""
    if source_name:
        print(f"Source:    {source_name}")
    print(f"Title:     {entry.get('title', 'N/A')}")
    print(f"Link:      {entry.get('link', 'N/A')}")
    print(f"Published: {entry.get('published', 'N/A')}")
    print()


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
        all_filtered.extend(filtered)

    if not all_filtered:
        print("No matching articles right now. Try again later!")
        return

    print("-" * 60)
    for article in all_filtered:
        display_article(article, source_name=article.get("_source", ""))


if __name__ == "__main__":
    main()
