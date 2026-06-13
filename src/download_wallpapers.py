"""
4kwallpapers.com batch wallpaper downloader
Downloads 4K (3840x2160) wallpapers from the site.

Strategy:
1. Scrape list pages to find wallpaper detail page links
2. Visit each detail page to get the 4K download URL
3. Download the image
"""

import os
import re
import time
import logging
import argparse
import concurrent.futures
from urllib.parse import urljoin, unquote

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://4kwallpapers.com"
DOWNLOAD_DIR = "wallpapers"
RESOLUTION = "3840x2160"  # 4K resolution

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("download.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/*;q=0.8,*/*;q=0.7",
    "Accept-Language": "en-US,en;q=0.5",
})


def is_detail_page_url(href: str) -> bool:
    """Check if a URL is a wallpaper detail page.
    Detail pages match: /category/name-id.html or https://4kwallpapers.com/category/name-id.html
    e.g. /technology/wwdc-2026-glow-all-26628.html
         https://4kwallpapers.com/black-dark/ducati-26499.html
    """
    pattern = r"(?:^https?://4kwallpapers\.com)?/[^/]+/[^/]+-\d+\.html$"
    return bool(re.match(pattern, href))


def get_list_page_urls(base_url: str, max_pages: int) -> list[str]:
    """Generate list page URLs."""
    pages = []
    for page_num in range(1, max_pages + 1):
        if page_num == 1:
            pages.append(base_url)
        else:
            sep = "&" if "?" in base_url else "?"
            pages.append(f"{base_url}{sep}page={page_num}")
    return pages


def parse_wallpaper_links(list_page_url: str) -> list[str]:
    """Parse wallpaper detail page links from a list page."""
    try:
        resp = session.get(list_page_url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to fetch list page {list_page_url}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    links = []

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if is_detail_page_url(href):
            full_url = urljoin(BASE_URL, href)
            if full_url not in links:
                links.append(full_url)

    return links


def parse_download_url(detail_page_url: str) -> tuple[str, str] | None:
    """Parse the 4K download URL from a wallpaper detail page."""
    try:
        resp = session.get(detail_page_url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to fetch detail page {detail_page_url}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # Find the 4K download link
    # Format: /images/wallpapers/name-3840x2160-id.png or full URL
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if f"-{RESOLUTION}-" in href and "/images/wallpapers/" in href:
            full_url = urljoin(BASE_URL, href)
            filename = os.path.basename(unquote(href))
            return full_url, filename

    # Fallback: try any download link with the resolution
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if RESOLUTION in href and "/images/wallpapers/" in href:
            full_url = urljoin(BASE_URL, href)
            filename = os.path.basename(unquote(href))
            return full_url, filename

    logger.warning(f"No {RESOLUTION} download found for {detail_page_url}")
    return None


def download_image(url: str, filepath: str, max_retries: int = 3) -> bool:
    """Download an image from URL to filepath with retry on 429."""
    if os.path.exists(filepath):
        logger.info(f"Already exists: {filepath}")
        return True

    for attempt in range(max_retries):
        try:
            resp = session.get(url, timeout=120, stream=True)
            if resp.status_code == 429:
                wait = 5 * (attempt + 1)
                logger.warning(f"Rate limited (429), retrying in {wait}s... (attempt {attempt+1}/{max_retries})")
                time.sleep(wait)
                continue
            resp.raise_for_status()

            temp_path = filepath + ".tmp"
            with open(temp_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

            os.rename(temp_path, filepath)
            size_mb = os.path.getsize(filepath) / (1024 * 1024)
            logger.info(f"Downloaded: {filepath} ({size_mb:.1f} MB)")
            return True

        except Exception as e:
            logger.error(f"Failed to download {url} (attempt {attempt+1}/{max_retries}): {e}")
            if os.path.exists(filepath + ".tmp"):
                os.remove(filepath + ".tmp")
            if attempt < max_retries - 1:
                time.sleep(3 * (attempt + 1))

    return False


def process_wallpaper(detail_url: str, output_dir: str) -> bool:
    """Process a single wallpaper: parse detail page and download."""
    result = parse_download_url(detail_url)
    if result is None:
        return False

    download_url, filename = result
    filepath = os.path.join(output_dir, filename)
    return download_image(download_url, filepath)


def get_category_links() -> list[str]:
    """Get category links from the homepage."""
    try:
        resp = session.get(BASE_URL, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to fetch homepage: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    categories = []

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        # Category links end with / e.g. /technology/, /cars/, /nature/
        # Or tag links like /dark-background, /5k
        full_url = urljoin(BASE_URL, href)
        if full_url.startswith(BASE_URL) and full_url != BASE_URL:
            if full_url not in categories:
                # Only include category pages (have sub-pages with wallpapers)
                path = full_url.replace(BASE_URL, "")
                if path.count("/") >= 1 and not path.endswith(".html"):
                    categories.append(full_url)

    return categories


def main():
    parser = argparse.ArgumentParser(description="4kwallpapers.com batch downloader")
    parser.add_argument("--pages", type=int, default=50, help="Number of list pages to scrape per category")
    parser.add_argument("--output", type=str, default=DOWNLOAD_DIR, help="Output directory")
    parser.add_argument("--workers", type=int, default=4, help="Number of download workers")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between requests (seconds)")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    # Step 1: Get category links from homepage
    logger.info("Fetching category links from homepage...")
    category_links = get_category_links()
    logger.info(f"Found {len(category_links)} category links")

    # Step 2: Collect all wallpaper detail links from category pages
    logger.info(f"Collecting wallpaper links from {args.pages} pages per category...")
    all_detail_urls = []
    seen = set()
    total_pages_scanned = 0

    for cat_url in category_links:
        if total_pages_scanned >= args.pages:
            break

        remaining = args.pages - total_pages_scanned
        list_pages = get_list_page_urls(cat_url, remaining)

        for i, page_url in enumerate(list_pages, 1):
            logger.info(f"Scanning page {total_pages_scanned + i}/{args.pages}: {page_url}")
            links = parse_wallpaper_links(page_url)
            new_links = [l for l in links if l not in seen]
            seen.update(new_links)
            all_detail_urls.extend(new_links)
            logger.info(f"  Found {len(new_links)} new wallpapers (total: {len(all_detail_urls)})")
            time.sleep(args.delay)

        total_pages_scanned += len(list_pages)

    logger.info(f"Total wallpaper detail pages found: {len(all_detail_urls)}")

    if not all_detail_urls:
        logger.error("No wallpapers found. Exiting.")
        return

    # Step 3: Download wallpapers
    logger.info(f"Starting download with {args.workers} workers...")
    success_count = 0
    fail_count = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {}
        for url in all_detail_urls:
            future = executor.submit(process_wallpaper, url, args.output)
            futures[future] = url
            time.sleep(args.delay / args.workers)

        for future in concurrent.futures.as_completed(futures):
            url = futures[future]
            try:
                if future.result():
                    success_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                logger.error(f"Error processing {url}: {e}")
                fail_count += 1

    logger.info(f"Download complete! Success: {success_count}, Failed: {fail_count}")
    logger.info(f"Files saved to: {os.path.abspath(args.output)}")


if __name__ == "__main__":
    main()
