#!/usr/bin/env python3
"""
seo-internal-link-analyzer/analyzer.py

Crawls an XML sitemap and audits internal linking structure.
Identifies orphan pages, weak pages, and missed link opportunities.

Author: Mehran Moghadasi
License: MIT
"""

import argparse
import csv
import os
import time
from collections import defaultdict
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
import networkx as nx
import pandas as pd

# ---------------------------------------------------------------------------
# CONFIG DEFAULTS
# ---------------------------------------------------------------------------
DEFAULT_MIN_INLINKS = 3
DEFAULT_MAX_DEPTH = 4
DEFAULT_CONCURRENCY = 3
DEFAULT_CRAWL_DELAY = 0.5  # seconds between requests
REQUEST_TIMEOUT = 10
USER_AGENT = "SEOInternalLinkAnalyzer/1.0 (github.com/mehranmoghadasi)"

HEADERS = {"User-Agent": USER_AGENT}


# ---------------------------------------------------------------------------
# SITEMAP PARSER
# ---------------------------------------------------------------------------
def parse_sitemap(sitemap_url: str) -> list:
    """
    Fetches and parses an XML sitemap (standard or sitemap index).
    Returns a flat list of page URLs.
    """
    print(f"[sitemap] Fetching: {sitemap_url}")
    resp = requests.get(sitemap_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "lxml-xml")

    # Sitemap index: recurse into child sitemaps
    sitemap_tags = soup.find_all("sitemap")
    if sitemap_tags:
        urls = []
        for tag in sitemap_tags:
            loc = tag.find("loc")
            if loc:
                urls.extend(parse_sitemap(loc.text.strip()))
        return urls

    # Standard sitemap
    url_tags = soup.find_all("url")
    return [tag.find("loc").text.strip() for tag in url_tags if tag.find("loc")]


# ---------------------------------------------------------------------------
# PAGE CRAWLER
# ---------------------------------------------------------------------------
def crawl_page(url: str, base_domain: str) -> dict:
    """
    Fetches a single page and extracts:
    - Internal links (href, rel, anchor text)
    - H2/H3 heading keywords for topic matching
    Returns a dict with page data, or None on error.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        print(f"  [warn] Failed to crawl {url}: {e}")
        return None

    # Extract internal links
    internal_links = []
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        abs_url = urljoin(url, href)
        parsed = urlparse(abs_url)
        if parsed.netloc == base_domain and parsed.scheme in ("http", "https"):
            rel = a_tag.get("rel", [])
            is_nofollow = "nofollow" in rel
            internal_links.append({
                "target": abs_url.split("?")[0].split("#")[0],
                "anchor": a_tag.get_text(strip=True)[:80],
                "nofollow": is_nofollow,
            })

    # Extract heading keywords for topic matching
    headings = []
    for tag in soup.find_all(["h2", "h3"]):
        text = tag.get_text(strip=True).lower()
        words = [w for w in text.split() if len(w) > 4]
        headings.extend(words)

    return {
        "url": url,
        "links": internal_links,
        "keywords": set(headings),
        "title": (soup.title.string.strip() if soup.title else url),
    }


# ---------------------------------------------------------------------------
# LINK GRAPH BUILDER
# ---------------------------------------------------------------------------
def build_link_graph(crawl_results: list):
    """Builds a directed graph where nodes are URLs and edges are internal links."""
    G = nx.DiGraph()
    url_set = {r["url"] for r in crawl_results if r}
    for result in crawl_results:
        if not result:
            continue
        G.add_node(result["url"])
        for link in result["links"]:
            if link["target"] in url_set and not link["nofollow"]:
                G.add_edge(result["url"], link["target"])
    return G


# ---------------------------------------------------------------------------
# ANALYSIS FUNCTIONS
# ---------------------------------------------------------------------------
def find_orphan_pages(G, sitemap_urls: list) -> list:
    """Returns sitemap URLs with zero incoming internal links."""
    return [
        url for url in sitemap_urls
        if url in G and G.in_degree(url) == 0
    ]


def find_weak_pages(G, min_inlinks: int) -> list:
    """Returns pages below the minimum inlink threshold."""
    weak = []
    for node in G.nodes():
        inlinks = G.in_degree(node)
        if 0 < inlinks < min_inlinks:
            weak.append({"url": node, "inlinks": inlinks})
    return sorted(weak, key=lambda x: x["inlinks"])


def find_link_opportunities(crawl_results: list, G) -> list:
    """
    Finds page pairs that share heading keywords but do not link to each other.
    These are high-value internal linking opportunities.
    """
    opportunities = []
    pages = [r for r in crawl_results if r and r["keywords"]]

    for i, page_a in enumerate(pages):
        for page_b in pages[i + 1:]:
            if G.has_edge(page_a["url"], page_b["url"]):
                continue
            if G.has_edge(page_b["url"], page_a["url"]):
                continue
            shared = page_a["keywords"] & page_b["keywords"]
            if len(shared) >= 2:
                opportunities.append({
                    "source": page_a["url"],
                    "target": page_b["url"],
                    "shared_keywords": ", ".join(list(shared)[:5]),
                    "shared_count": len(shared),
                })

    return sorted(opportunities, key=lambda x: -x["shared_count"])


# ---------------------------------------------------------------------------
# REPORT EXPORT
# ---------------------------------------------------------------------------
def save_csv(data: list, filepath: str):
    """Saves a list of dicts to CSV."""
    if not data:
        print(f"  [skip] No data for {filepath}")
        return
    df = pd.DataFrame(data)
    df.to_csv(filepath, index=False)
    print(f"  [saved] {filepath} ({len(df)} rows)")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="SEO Internal Link Analyzer")
    parser.add_argument("--sitemap", required=True, help="URL of the XML sitemap")
    parser.add_argument("--min-inlinks", type=int, default=DEFAULT_MIN_INLINKS)
    parser.add_argument("--max-depth", type=int, default=DEFAULT_MAX_DEPTH)
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    parser.add_argument("--output", default="./reports/", help="Output directory")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    base_domain = urlparse(args.sitemap).netloc

    # Phase 1: Parse sitemap
    sitemap_urls = parse_sitemap(args.sitemap)
    print(f"\n[info] Found {len(sitemap_urls)} URLs in sitemap")

    # Phase 2: Crawl pages
    print(f"[info] Crawling pages (delay: {DEFAULT_CRAWL_DELAY}s)...")
    crawl_results = []
    for i, url in enumerate(sitemap_urls):
        print(f"  [{i+1}/{len(sitemap_urls)}] {url}")
        result = crawl_page(url, base_domain)
        crawl_results.append(result)
        time.sleep(DEFAULT_CRAWL_DELAY)

    successful = [r for r in crawl_results if r]
    print(f"[info] Successfully crawled: {len(successful)}/{len(sitemap_urls)}")

    # Phase 3: Build graph and analyze
    G = build_link_graph(crawl_results)
    orphans = find_orphan_pages(G, sitemap_urls)
    weak_pages = find_weak_pages(G, args.min_inlinks)
    opportunities = find_link_opportunities(crawl_results, G)

    # Phase 4: Print summary
    print(f"\n=== SEO Internal Link Report - {base_domain} ===")
    print(f"Total URLs in sitemap:       {len(sitemap_urls)}")
    print(f"Pages crawled successfully:  {len(successful)}")
    print(f"Orphan pages found:          {len(orphans)}")
    print(f"Weak pages (< {args.min_inlinks} inlinks):    {len(weak_pages)}")
    print(f"Link opportunities found:    {len(opportunities)} page pairs")

    if orphans:
        print(f"\nTop 5 Orphan Pages:")
        for url in orphans[:5]:
            print(f"  {url}")

    # Phase 5: Export CSV
    save_csv([{"url": u} for u in orphans], os.path.join(args.output, "orphans.csv"))
    save_csv(weak_pages, os.path.join(args.output, "weak_pages.csv"))
    save_csv(opportunities[:100], os.path.join(args.output, "link_opportunities.csv"))
    print(f"\n[done] Reports saved to: {args.output}")


if __name__ == "__main__":
    main()
