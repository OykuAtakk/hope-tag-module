import requests
import random
import time
import json
import re
import ssl
import socket
import multiprocessing
from datetime import datetime
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse, urljoin

import cloudscraper
from bs4 import BeautifulSoup
import whois
from dateutil import parser
from playwright.sync_api import sync_playwright

# ---------------- Constants & Global Variables ---------------- #

SLEEP_DELAY = 5
RETRY_ATTEMPTS = 5

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:90.0) Gecko/20100101 Firefox/90.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edge/91.0.864.59"
]

COOKIES = [
    {"name": "time_zone", "value": "GMT+3", "domain": "example.com", "path": "/"},
    {"name": "daily_visit_count", "value": "5", "domain": "example.com", "path": "/"},
    {"name": "last_purchase", "value": "2024-11-01", "domain": "example.com", "path": "/"},
    {"name": "device_type", "value": "mobile", "domain": "example.com", "path": "/"},
    {"name": "trial_expiry", "value": "2024-12-01", "domain": "example.com", "path": "/"},
    {"name": "visited_tutorial", "value": "true", "domain": "example.com", "path": "/"},
    {"name": "notification_preference", "value": "email", "domain": "example.com", "path": "/"},
    {"name": "region", "value": "North_America", "domain": "example.com", "path": "/"},
    {"name": "vip_status", "value": "gold", "domain": "example.com", "path": "/"},
    {"name": "referral_code", "value": "XYZ1234", "domain": "example.com", "path": "/"}
]

not_found_urls = []
whois_error_urls = []  # Hata durumları için (ileride doldurulabilir)


# ---------------- Utility Fonksiyonlar ---------------- #

def ensure_url_scheme(url):
    """
    URL'nin 'http://' veya 'https://' ile başladığından emin olur.
    """
    return url if url.startswith(('http://', 'https://')) else 'http://' + url


def clean_text(text):
    """
    Metni temizler; istenmeyen karakterleri kaldırır ve boşlukları virgülle ayrılmış forma dönüştürür.
    """
    text = re.sub(r"(\w+)' (\w+)", r"\1, \2", text)
    text = re.sub(r"'", "", text)
    text = re.sub(r"[^a-zA-Z0-9çÇğĞıİöÖşŞüÜ ]", "", text)
    return ",".join(text.split()).strip()


def decode_response_content(response):
    """
    HTTP yanıtını, belirlenen kodlamaya göre çözümler.
    """
    try:
        return response.content.decode(response.apparent_encoding)
    except Exception as e:
        print(f"Error decoding content: {e}")
        return response.text


def get_random_content(content, length=300):
    """
    Temizlenmiş metinden, karıştırılmış kelimelerden oluşturulmuş
    belirtilen uzunlukta (default 300 karakter) bir içerik parçası döndürür.
    """
    cleaned = clean_text(content)
    words = cleaned.split(',')
    if len(' '.join(words)) < length:
        return cleaned
    random.shuffle(words)
    return ','.join(words)[:length]


def has_ssl_certificate(url):
    """
    Verilen URL için geçerli bir SSL sertifikası olup olmadığını kontrol eder.
    """
    parsed = urlparse(url)
    host = parsed.hostname
    port = 443
    try:
        context = ssl.create_default_context()
        with socket.create_connection((host, port)) as conn:
            with context.wrap_socket(conn, server_hostname=host) as ssock:
                ssock.getpeercert()
                return True
    except Exception:
        return False


def get_dynamic_thread_count():
    """
    Sistemdeki CPU çekirdeklerine göre kullanılacak iş parçacığı sayısını belirler.
    """
    return max(2, multiprocessing.cpu_count() // 2)


def get_site_age(url):
    """
    Whois bilgisinden domain'in oluşturulma tarihine bakarak yaşını (yıl olarak) hesaplar.
    """
    try:
        domain_info = whois.whois(url)
        creation_date = domain_info.creation_date
        if isinstance(creation_date, list):
            creation_date = creation_date[0]
        if isinstance(creation_date, str):
            creation_date = parser.parse(creation_date)
        if isinstance(creation_date, datetime):
            return datetime.now().year - creation_date.year
        print("Creation date is not available or not in expected format.")
    except Exception as e:
        print(f"Error getting site age for {url}: {e}")
    return None


def get_last_updated_date(url):
    """
    Web sitesinin en son güncellendiği tarihi meta tag'ler, metin, scriptler, HTTP header veya sitemap üzerinden çıkarmaya çalışır.
    """
    url = ensure_url_scheme(url)
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content.decode('utf-8', 'ignore'), "html.parser")

        # Meta tag'leri kontrol et
        for meta in [{'name': 'last-modified'}, {'property': 'og:updated_time'}]:
            tag = soup.find('meta', meta)
            if tag and tag.get('content'):
                try:
                    date = datetime.strptime(tag['content'], '%Y-%m-%dT%H:%M:%S')
                    return {"year": date.year, "month": date.month}
                except ValueError:
                    continue

        # Sayfa metninde tarih araması
        for text in ["son güncelleme", "last updated", "last modified", "güncellendi"]:
            found = soup.find(string=re.compile(text, re.IGNORECASE))
            if found:
                match = re.search(r'\b\d{4}-\d{2}-\d{2}\b', found)
                if match:
                    date = datetime.strptime(match.group(), '%Y-%m-%d')
                    return {"year": date.year, "month": date.month}

        # Script içeriğinde tarih araması
        date_pattern = re.compile(r'\b(\d{4})-(\d{2})-\d{2}\b|\b(\d{2})/(\d{2})/(\d{4})\b')
        for script in soup.find_all('script'):
            if script.string:
                match = date_pattern.search(script.string)
                if match:
                    if match.group(1) and match.group(2):
                        year, month = int(match.group(1)), int(match.group(2))
                    elif match.group(5) and match.group(4):
                        year, month = int(match.group(5)), int(match.group(4))
                    return {"year": year, "month": month}

        # HTTP Header üzerinden Last-Modified kontrolü
        if 'Last-Modified' in response.headers:
            try:
                date = datetime.strptime(response.headers['Last-Modified'], '%a, %d %b %Y %H:%M:%S %Z')
                return {"year": date.year, "month": date.month}
            except ValueError:
                pass

        # Sitemap üzerinden kontrol
        sitemap_url = url.rstrip('/') + "/sitemap.xml"
        sitemap_resp = requests.get(sitemap_url, timeout=10)
        if sitemap_resp.status_code == 200:
            sitemap_soup = BeautifulSoup(sitemap_resp.content, 'xml')
            lastmod = sitemap_soup.find('lastmod')
            if lastmod:
                try:
                    date = datetime.strptime(lastmod.text.strip(), '%Y-%m-%d')
                    return {"year": date.year, "month": date.month}
                except ValueError:
                    pass

    except requests.exceptions.RequestException as e:
        print(f"Error fetching last updated date for {url}: {e}")
    return {"year": None, "month": None}

def extract_external_backlinks(soup, base_url):
    """
    Sayfadaki tüm 'a' etiketlerini tarayarak,
    eğer link, base_url'nin domain'ine ait değilse (yani dış backlink ise)
    liste olarak döndürür.
    """
    backlinks = []
    base_domain = urlparse(base_url).netloc.lower()
    for tag in soup.find_all('a', href=True):
        href = tag.get('href')
        absolute_url = urljoin(base_url, href)
        link_domain = urlparse(absolute_url).netloc.lower()
        # Eğer link kendi domain'indeyse veya boşsa atla.
        if link_domain and link_domain != base_domain:
            backlinks.append(absolute_url)
    return list(set(backlinks))  # Yinelenenleri kaldırır


# ---------------- Playwright ile Dinamik İçerik Çekme ---------------- #

def fetch_and_parse(url):
    """
    Playwright kullanarak dinamik olarak JavaScript ile yüklenen sayfa içeriğini çeker.
    """
    with sync_playwright() as p:
        # headless=False yerine üretimde True kullanmanız önerilir.
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=30000)
        page.wait_for_timeout(5000)  # 5 saniye bekle
        html_content = page.content()
        browser.close()
        return html_content


# ---------------- Ana İşlem Fonksiyonları ---------------- #

def tag_website(_id, url, use_playwright=False):
    """
    Verilen URL üzerinde çeşitli verileri (HTML etiketleri, yüklenme süresi, SSL durumu, domain yaşı, vb.) çıkarır.
    Eğer use_playwright True ise, dinamik içeriği çekmek için Playwright kullanır.
    """
    url = ensure_url_scheme(url)
    start_time = time.time()

    if use_playwright:
        # Playwright ile dinamik içerik alınır
        try:
            html_content = fetch_and_parse(url)
            soup = BeautifulSoup(html_content, "html.parser")
            load_time = round(time.time() - start_time, 2)
        except Exception as e:
            print(f"Playwright ile içerik çekilirken hata oluştu {url}: {e}")
            return {"url": url, "ssl_certificate": False, "error": str(e)}
    else:
        # cloudscraper ile statik içerik alınır
        scraper = cloudscraper.create_scraper()
        selected_cookie = random.choice(COOKIES)
        cookie_data = {selected_cookie["name"]: selected_cookie["value"]}
        headers = {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive'
        }

        for attempt in range(RETRY_ATTEMPTS):
            try:
                response = scraper.get(url, timeout=15 + min(attempt * 5, 30), cookies=cookie_data, headers=headers)
                response.raise_for_status()
                load_time = round(time.time() - start_time, 2)
                html_content = response.content.decode('utf-8', 'ignore')
                soup = BeautifulSoup(html_content, "html.parser")

                # Cloudflare kontrolü
                if any(phrase in response.text for phrase in ["Attention", "Just a moment", "Checking your browser"]):
                    print(f"Cloudflare koruması ile karşılaşıldı {url}. Bekleniyor...")
                    time.sleep(1800)
                break  # Başarılı ise döngüden çık
            except requests.RequestException as e:
                if '404' in str(e):
                    not_found_urls.append(url)
                if attempt < RETRY_ATTEMPTS - 1:
                    wait_time = random.uniform(3, 6)
                    print(f"Timeout/error for {url}. Retrying in {wait_time:.2f} seconds...")
                    time.sleep(wait_time)
                else:
                    print(f"Error fetching {url}: {e}")
                    return {"url": url, "ssl_certificate": False, "error": str(e)}
            except Exception as e:
                print(f"Unexpected error for {url}: {e}")
                return {"url": url, "ssl_certificate": False, "error": str(e)}

    h1_tags = [clean_text(tag.get_text().strip()) for tag in soup.find_all('h1')]
    h2_tags = [clean_text(tag.get_text().strip()) for tag in soup.find_all('h2')]
    h3_tags = [clean_text(tag.get_text().strip()) for tag in soup.find_all('h3')]
    title_tag = clean_text(soup.title.string.strip()) if soup.title and soup.title.string else ""
    meta_tag = soup.find("meta", attrs={"name": "description"})
    meta_description = clean_text(meta_tag["content"].strip()) if meta_tag and meta_tag.get("content") else ""
    ssl_valid = has_ssl_certificate(url)
    last_updated = get_last_updated_date(url)
    mobile_compatible = bool(soup.find('meta', attrs={'name': 'viewport'}))
    domain_age = get_site_age(url)
    content = soup.get_text(strip=True)
    random_content = get_random_content(content, length=300)
    strong_texts = [tag.get_text(strip=True) for tag in soup.find_all("strong")]
    underline_texts = [tag.get_text(strip=True) for tag in soup.find_all("u")]

    external_backlinks = extract_external_backlinks(soup, url)

    return {
        "_id": _id,
        "url": url,
        "h1_keyword": h1_tags,
        "h2_keyword": h2_tags,
        "h3_keyword": h3_tags,
        "title_keyword": title_tag,
        "meta_keyword": meta_description,
        "load_time": load_time,
        "last_update_year": last_updated["year"],
        "last_update_month": last_updated["month"],
        "mobile_compatibility": mobile_compatible,
        "ssl_certificate": ssl_valid,
        "site_age": domain_age,
        "processed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "random_content": random_content,
        "strong_texts": strong_texts,
        "underline_texts": underline_texts,
        "external_backlinks": external_backlinks
    }


def process_with_delay(args, use_playwright=False):
    """
    Belirli bir bekleme süresinin ardından tag_website fonksiyonunu çağırır.
    """
    _id, url = args
    time.sleep(SLEEP_DELAY)
    return tag_website(_id, url, use_playwright=use_playwright)


# ---------------- Ana Çalıştırma Bloğu ---------------- #

if __name__ == "__main__":
    # JSON verisini yükle
    with open('veriler2.json', 'r', encoding='utf-8') as file:
        veriler = json.load(file)

    thread_count = get_dynamic_thread_count()
    print(f"Kullanılan iş parçacığı sayısı: {thread_count}")

    # Dinamik içerik çekmek için use_playwright parametresini True yapabilirsiniz.
    args_list = [(veri['_id'], veri['url']) for veri in veriler]
    with ThreadPoolExecutor(max_workers=thread_count) as executor:
        results = list(executor.map(lambda args: process_with_delay(args, use_playwright=True), args_list))

    # Hata içermeyen sonuçları filtrele
    sonuclar = [result for result in results if result and "error" not in result]

    # Sonuçları JSON dosyalarına kaydet
    with open('not_found_urls.json', 'w', encoding='utf-8') as nf_file:
        json.dump(not_found_urls, nf_file, ensure_ascii=False, indent=4)
    with open('whois_error_urls.json', 'w', encoding='utf-8') as we_file:
        json.dump(whois_error_urls, we_file, ensure_ascii=False, indent=4)
    with open('sonuclar2.json', 'w', encoding='utf-8') as output_file:
        json.dump(sonuclar, output_file, ensure_ascii=False, indent=4)

    print("Sonuçlar 'sonuclar2.json' dosyasına kaydedildi.")
    print("404 hatası veren URL'ler 'not_found_urls.json' dosyasına kaydedildi.")
    print("Whois hatası veren URL'ler 'whois_error_urls.json' dosyasına kaydedildi.")
