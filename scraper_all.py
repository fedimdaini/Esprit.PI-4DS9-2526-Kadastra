import requests
from bs4 import BeautifulSoup
import csv
import time
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

OUTPUT_FILE    = "articles_all.csv"
DELAY          = 1.5
MAX_YEARS_BACK = 3
DATE_LIMIT     = datetime.now().replace(year=datetime.now().year - MAX_YEARS_BACK)

HEADERS_HTTP = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Liste des sites à scraper
SITES = [
    {
        "name":     "webdo.tn",
        "engine":   "requests",
        "base_url": "https://www.webdo.tn",
        "category": "https://www.webdo.tn/fr/actualites/divers",
        "pagination": "wordpress_page",   # /page/N/
    },
    {
        "name":     "mosaiquefm.net",
        "engine":   "selenium",
        "base_url": "https://www.mosaiquefm.net",
        "category": "https://www.mosaiquefm.net/fr/actualites/actualite-faits-divers/14",
        "pagination": "slash",            # /N
    },
    {
        "name":     "letemps.news",
        "engine":   "requests",
        "base_url": "https://letemps.news",
        "category": "https://letemps.news/category/societe/faits-divers",
        "pagination": "wordpress_page",
    },
    {
        "name":     "kapitalis.com",
        "engine":   "requests",
        "base_url": "https://kapitalis.com",
        "category": "https://kapitalis.com/tunisie/category/societe",
        "pagination": "wordpress_page",
    },
]

# ═══════════════════════════════════════════════════════════════════════════════
# UTILITAIRES DATE
# ═══════════════════════════════════════════════════════════════════════════════

MOIS_FR = {
    "janvier":1,"février":2,"mars":3,"avril":4,"mai":5,"juin":6,
    "juillet":7,"août":8,"septembre":9,"octobre":10,"novembre":11,"décembre":12,
}

def parse_date_fr(date_str):
    """Parse '29 janvier 2026' ou 'jeudi 29 janvier 2026 12:15'"""
    try:
        parts = date_str.strip().lower().split()
        if parts[0] in ["lundi","mardi","mercredi","jeudi","vendredi","samedi","dimanche"]:
            parts = parts[1:]
        return datetime(int(parts[2]), MOIS_FR.get(parts[1], 0), int(parts[0]))
    except Exception:
        return None

def parse_date_slash(date_str):
    """Parse '2024/11/13 13:42'"""
    try:
        return datetime.strptime(date_str.strip()[:10], "%Y/%m/%d")
    except Exception:
        return None

def parse_date_iso(date_str):
    """Parse '2025-03-03T14:02:24+01:00'"""
    try:
        return datetime.strptime(date_str.strip()[:10], "%Y-%m-%d")
    except Exception:
        return None

# ═══════════════════════════════════════════════════════════════════════════════
# PAGINATION
# ═══════════════════════════════════════════════════════════════════════════════

def get_page_url(site, page):
    if page == 1:
        return site["category"]
    if site["pagination"] == "wordpress_page":
        return f"{site['category']}/page/{page}/"
    if site["pagination"] == "slash":
        return f"{site['category']}/{page}"

# ═══════════════════════════════════════════════════════════════════════════════
# SELENIUM
# ═══════════════════════════════════════════════════════════════════════════════

def init_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    return webdriver.Chrome(options=options)

def get_soup_selenium(driver, url, wait=4):
    driver.get(url)
    time.sleep(wait)
    return BeautifulSoup(driver.page_source, "html.parser")

def get_soup_requests(url):
    response = requests.get(url, headers=HEADERS_HTTP, timeout=10)
    return BeautifulSoup(response.text, "html.parser")

# ═══════════════════════════════════════════════════════════════════════════════
# SCRAPING LISTE — par site
# ═══════════════════════════════════════════════════════════════════════════════

def get_links_webdo(soup):
    items = []
    for article in soup.select("article.jeg_post"):
        a       = article.select_one("h3.jeg_post_title a")
        date_el = article.select_one(".jeg_meta_date a")
        if a and a.get("href"):
            date_text = date_el.get_text(strip=True) if date_el else ""
            items.append({"url": a["href"], "date_text": date_text, "date_parsed": parse_date_fr(date_text)})
    return items

def get_links_mosaique(soup, base_url):
    items = []
    seen  = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/fr/actualite-faits-divers/" not in href:
            continue
        url = href if href.startswith("http") else base_url + href
        if url in seen:
            continue
        seen.add(url)
        parent    = a.find_parent(class_="item") or a.find_parent("article")
        time_el   = parent.find("time") if parent else None
        date_text = time_el.get_text(strip=True) if time_el else ""
        items.append({"url": url, "date_text": date_text, "date_parsed": parse_date_slash(date_text)})
    return items

def get_links_letemps(soup):
    items = []
    for article in soup.select("article.l-post"):
        a       = article.select_one("h2.post-title a")
        time_el = article.select_one("time.post-date")
        if a and a.get("href"):
            date_text     = time_el.get_text(strip=True) if time_el else ""
            datetime_attr = time_el.get("datetime", "") if time_el else ""
            items.append({"url": a["href"], "date_text": date_text, "date_parsed": parse_date_iso(datetime_attr)})
    return items

def get_links_kapitalis(soup):
    items = []
    for article in soup.select("article.cmsmasters_archive_type"):
        a       = article.select_one("h2.cmsmasters_archive_item_title a")
        date_el = article.select_one("abbr.cmsmasters_archive_item_date")
        if a and a.get("href"):
            date_text = date_el.get_text(strip=True) if date_el else ""
            items.append({"url": a["href"], "date_text": date_text, "date_parsed": parse_date_fr(date_text)})
    return items

# ═══════════════════════════════════════════════════════════════════════════════
# SCRAPING ARTICLE — par site
# ═══════════════════════════════════════════════════════════════════════════════

def scrape_webdo(soup, url):
    title   = soup.select_one("h1.jeg_post_title")
    title   = title.get_text(strip=True) if title else ""
    date_el = soup.select_one(".jeg_meta_date a")
    date    = date_el.get_text(strip=True) if date_el else ""
    paragraphs = []
    for p in soup.select(".content-inner p"):
        if p.find_parent("blockquote"):
            continue
        text = p.get_text(strip=True)
        if text:
            paragraphs.append(text)
    tags = [a.get_text(strip=True) for a in soup.select(".jeg_post_tags a[rel='tag']")]
    return {"url": url, "source": "webdo.tn", "title": title, "date": date,
            "description": " ".join(paragraphs), "tags": "|".join(tags)}

def scrape_mosaique(soup, url):
    art     = soup.select_one("article.article")
    title   = art.select_one("h1.pageTitle") if art else None
    title   = title.get_text(strip=True) if title else ""
    date_el = art.select_one("time.dateTime") if art else None
    date    = date_el.get_text(strip=True) if date_el else ""
    paragraphs = []
    if art:
        for p in art.select("p"):
            if p.find_parent(class_="tags"):
                continue
            text = p.get_text(strip=True)
            if text:
                paragraphs.append(text)
    tags = []
    if art:
        tags_div = art.select_one("div.tags")
        if tags_div:
            tags = [a.get_text(strip=True).rstrip(",") for a in tags_div.select("a")]
    return {"url": url, "source": "mosaiquefm.net", "title": title, "date": date,
            "description": " ".join(paragraphs), "tags": "|".join(tags)}

def scrape_letemps(soup, url):
    title   = soup.select_one("h1.post-title, h1.is-title")
    title   = title.get_text(strip=True) if title else ""
    date_el = soup.select_one("time.post-date")
    date    = date_el.get_text(strip=True) if date_el else ""
    paragraphs = []
    for p in soup.select("div.post-content p, div.entry-content p"):
        text = p.get_text(strip=True)
        if text:
            paragraphs.append(text)
    tags = [a.get_text(strip=True) for a in soup.select("div.the-post-tags a[rel='tag']")]
    return {"url": url, "source": "letemps.news", "title": title, "date": date,
            "description": " ".join(paragraphs), "tags": "|".join(tags)}

def scrape_kapitalis(soup, url):
    art     = soup.select_one("article.cmsmasters_open_post")
    title   = art.select_one("h1.cmsmasters_post_title") if art else None
    title   = title.get_text(strip=True) if title else ""
    date_el = art.select_one("abbr.published") if art else None
    date    = date_el.get_text(strip=True) if date_el else ""
    paragraphs = []
    if art:
        content = art.select_one("div.cmsmasters_post_content")
        if content:
            for p in content.select("p"):
                text = p.get_text(strip=True)
                if text:
                    paragraphs.append(text)
    tags = []
    if art:
        tags_span = art.select_one("span.cmsmasters_post_tags")
        if tags_span:
            tags = [a.get_text(strip=True) for a in tags_span.select("a[rel='tag']")]
    return {"url": url, "source": "kapitalis.com", "title": title, "date": date,
            "description": " ".join(paragraphs), "tags": "|".join(tags)}

# Dispatch
SCRAPE_FN = {
    "webdo.tn":       scrape_webdo,
    "mosaiquefm.net": scrape_mosaique,
    "letemps.news":   scrape_letemps,
    "kapitalis.com":  scrape_kapitalis,
}

LINKS_FN = {
    "webdo.tn":       lambda soup, site: get_links_webdo(soup),
    "mosaiquefm.net": lambda soup, site: get_links_mosaique(soup, site["base_url"]),
    "letemps.news":   lambda soup, site: get_links_letemps(soup),
    "kapitalis.com":  lambda soup, site: get_links_kapitalis(soup),
}

# ═══════════════════════════════════════════════════════════════════════════════
# SCRAPING D'UN SITE
# ═══════════════════════════════════════════════════════════════════════════════

def scrape_site(site, driver=None):
    print(f"\n{'═'*60}")
    print(f"🌐 Site : {site['name']}")
    print(f"{'═'*60}")

    all_articles = []
    stop         = False
    page         = 1
    use_selenium = site["engine"] == "selenium"

    while not stop:
        page_url = get_page_url(site, page)

        try:
            if use_selenium:
                soup = get_soup_selenium(driver, page_url)
            else:
                soup = get_soup_requests(page_url)
        except Exception as e:
            print(f"❌ Impossible de charger la page {page} : {e}")
            break

        items = LINKS_FN[site["name"]](soup, site)

        if not items:
            print(f"⚠️  Aucun article sur la page {page}, arrêt.")
            break

        print(f"📄 Page {page} — {len(items)} articles trouvés\n")

        for i, item in enumerate(items, 1):
            if item["date_parsed"] and item["date_parsed"] < DATE_LIMIT:
                print(f"  ⏹️  Article du {item['date_text']} trop ancien — arrêt.")
                stop = True
                break

            print(f"  [{i}/{len(items)}] {item['url']}")
            try:
                if use_selenium:
                    art_soup = get_soup_selenium(driver, item["url"], wait=3)
                else:
                    art_soup = get_soup_requests(item["url"])

                article = SCRAPE_FN[site["name"]](art_soup, item["url"])
                all_articles.append(article)
                print(f"    ✅ {article['title'][:70]}")
                print(f"    📅 {article['date']}  🏷️  {article['tags'] or 'Aucun tag'}")
            except Exception as e:
                print(f"    ❌ Erreur : {e}")
                all_articles.append({"url": item["url"], "source": site["name"],
                                     "title": "", "date": "", "description": "", "tags": f"ERREUR: {e}"})

            time.sleep(DELAY)

        print(f"\n  --- Page {page} terminée ---")
        if not stop:
            page += 1
            time.sleep(DELAY * 2)

    print(f"\n✅ {site['name']} : {len(all_articles)} articles scrapés")
    return all_articles

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("🚀 Démarrage du scraper unifié")
    print(f"📅 Limite : articles depuis le {DATE_LIMIT.strftime('%d/%m/%Y')}")
    print(f"🌐 Sites  : {', '.join(s['name'] for s in SITES)}\n")

    # Initialiser Selenium une seule fois (pour mosaique)
    driver = None
    needs_selenium = any(s["engine"] == "selenium" for s in SITES)
    if needs_selenium:
        print("🔧 Initialisation de Selenium...\n")
        driver = init_driver()

    all_articles = []

    try:
        for site in SITES:
            articles = scrape_site(site, driver=driver)
            all_articles.extend(articles)
    finally:
        if driver:
            driver.quit()

    # Sauvegarde CSV
    with open(OUTPUT_FILE, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["source", "url", "title", "date", "description", "tags"],
            delimiter=";"
        )
        writer.writeheader()
        writer.writerows(all_articles)

    print(f"\n{'═'*60}")
    print(f"✅ Scraping terminé !")
    print(f"📊 {len(all_articles)} articles scrapés au total")
    for site in SITES:
        count = sum(1 for a in all_articles if a.get("source") == site["name"])
        print(f"   • {site['name']} : {count} articles")
    print(f"💾 Résultats sauvegardés dans : {OUTPUT_FILE}")
    print(f"{'═'*60}")

if __name__ == "__main__":
    main()
