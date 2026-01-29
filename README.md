# Seed Funding Tracker

A simple Python script that fetches the TechCrunch RSS feed and filters for articles that mention **both** seed funding **and** AI / artificial intelligence.

## Setup

1. Make sure you have Python 3.8+ installed.

2. Create a virtual environment (optional but recommended):

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Usage

```bash
python main.py
```

The script will print any matching articles with their title, link, and publish date.

## How it works

- Uses `feedparser` to download and parse TechCrunch's RSS feed.
- Searches each article's title and summary for seed-funding keywords ("seed funding", "seed round", etc.).
- Also checks for AI keywords ("artificial intelligence", "ai").
- Only shows articles that match **both** categories.
