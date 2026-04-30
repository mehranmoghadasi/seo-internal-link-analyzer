# SEO Internal Link Analyzer

> Audit your site's internal linking structure in minutes, not hours.

[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://python.org)

## The Problem

Weak internal linking silently kills your SEO. Orphan pages get no PageRank. Deep pages stay buried. Most SEO platforms charge $300+/month to surface these issues — and still don't give you actionable link suggestions.

## The Solution

`seo-internal-link-analyzer` parses your XML sitemap, crawls each URL, extracts all internal links, builds a link graph, and identifies:

- **Orphan pages** — URLs in the sitemap with zero incoming internal links
- **Weak pages** — URLs with fewer than 3 incoming links (configurable)
- **Link opportunity pairs** — pages that share H2/H3 topic keywords but do not link to each other
- **Deep pages** — URLs more than 3 clicks from the homepage

Results export to CSV, ready to paste into your editorial backlog.

## Features

- Parses standard and index XML sitemaps
- Respects `robots.txt` crawl delay
- Detects nofollow vs. dofollow internal links
- Generates a link-opportunity matrix based on shared heading keywords
- Configurable depth limit, concurrency, and minimum inlink threshold
- Outputs: `orphans.csv`, `weak_pages.csv`, `link_opportunities.csv`

## Tech Stack

- Python 3.8+
- `requests` — HTTP fetching
- `beautifulsoup4` — HTML parsing
- `lxml` — XML sitemap parsing
- `networkx` — link graph analysis
- `pandas` — CSV export

## Installation

```bash
git clone https://github.com/mehranmoghadasi/seo-internal-link-analyzer.git
cd seo-internal-link-analyzer
pip install -r requirements.txt
```

## Usage

```bash
# Basic audit
python analyzer.py --sitemap https://example.com/sitemap.xml

# With custom settings
python analyzer.py \
  --sitemap https://example.com/sitemap.xml \
  --min-inlinks 3 \
  --max-depth 4 \
  --concurrency 5 \
  --output ./reports/
```

## Sample Output

```
=== SEO Internal Link Report — example.com ===
Total URLs in sitemap:       142
Pages crawled successfully:  138
Orphan pages found:           23  ← zero incoming internal links
Weak pages (< 3 inlinks):    41
Link opportunities found:     87 page pairs sharing topic keywords

Top 5 Orphan Pages:
  /blog/local-seo-guide-2024/
  /services/reputation-management/
  /case-studies/fintech-client/
  /blog/google-ads-quality-score/
  /resources/seo-checklist/

Reports saved to: ./reports/
  orphans.csv
  weak_pages.csv
  link_opportunities.csv
```

## MIT License

Copyright (c) 2026 Mehran Moghadasi

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software.
