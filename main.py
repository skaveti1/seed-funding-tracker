import feedparser

FEED_URL = "https://techcrunch.com/feed/"

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


def display_article(entry):
    """Print a single article's details."""
    print(f"Title:     {entry.get('title', 'N/A')}")
    print(f"Link:      {entry.get('link', 'N/A')}")
    print(f"Published: {entry.get('published', 'N/A')}")
    print()


def main():
    print("Fetching TechCrunch RSS feed...\n")
    entries = fetch_feed(FEED_URL)

    if not entries:
        print("No entries found in the feed.")
        return

    print(f"Total articles in feed: {len(entries)}")

    filtered = filter_articles(entries)
    print(f"Articles about AI + seed funding: {len(filtered)}\n")

    if not filtered:
        print("No matching articles right now. Try again later!")
        return

    print("-" * 60)
    for article in filtered:
        display_article(article)


if __name__ == "__main__":
    main()
