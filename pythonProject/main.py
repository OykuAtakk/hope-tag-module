import requests
from bs4 import BeautifulSoup
import cloudscraper
import os
import random
import time
from datetime import datetime
import re
import json
import whois
from concurrent.futures import ThreadPoolExecutor
from dateutil import parser
from collections import deque
import ssl
import socket
from urllib.parse import urlparse
import multiprocessing
from playwright.sync_api import sync_playwright


def get_random_content(content, length=300):
    # İçeriği temizle
    cleaned_content = clean_text(content)

    # Kelimeleri listeye ayır
    words = cleaned_content.split(',')

    # Eğer kelimeler yeterince uzun değilse hata ver
    if len(' '.join(words)) < length:
        return cleaned_content

    # Kelimeleri karıştır
    random.shuffle(words)  # Tüm kelimeleri karıştır

    # Karıştırılan kelimeleri virgüllerle birleştir
    random_content = ','.join(words)

    # 300 karakterlik kısmı al
    result = random_content[:length]  # 300 karaktere kadar al

    return result

def ensure_url_scheme(url):
    if not url.startswith(('http://', 'https://')):
        return 'http://' + url
    return url
def has_ssl_certificate(url):
    # URL'nin host kısmını almak için urlparse kullanıyoruz
    parsed_url = urlparse(url)
    host = parsed_url.hostname
    port = 443  # HTTPS portu

    try:
        # Socket ile HTTPS bağlantısı kuruyoruz
        context = ssl.create_default_context()
        with socket.create_connection((host, port)) as conn:
            with context.wrap_socket(conn, server_hostname=host) as ssock:
                # SSL sertifikası alınıyor
                ssock.getpeercert()
                return True  # Sertifika var
    except Exception:
        return False  # Sertifika yok veya bağlantı hatalı

def get_dynamic_thread_count():
    cpu_count = multiprocessing.cpu_count()
    return max(2, cpu_count // 2)
def decode_response_content(response):
    try:
        encoding = response.apparent_encoding
        return response.content.decode(encoding)
    except Exception as e:
        print(f"Error decoding content: {e}")
        return response.text

def clean_text(text):
    # Kesme işaretinden sonra boşluk varsa, kesme işaretine kadar olan kısmı kaldır
    text = re.sub(r"(\w+)' (\w+)", r"\1, \2", text)
    # Kelimenin sonunda kesme işareti varsa sadece kesme işareti kaldır
    text = re.sub(r"'", "", text)
    # Özel karakterleri kaldır
    text = re.sub(r"[^a-zA-Z0-9çÇğĞıİöÖşŞüÜ ]", "", text)
    # Kelimeler arsına boşluk yerine virgül atar
    text = ",".join(text.split())
    return text.strip()

def get_site_age(url):
    try:
        # URL'den domain bilgisini alıyoruz
        domain_info = whois.whois(url)
        creation_date = domain_info.creation_date
        print(creation_date)

        # Eğer creation_date bir listeyse, ilk elemanı alıyoruz
        if isinstance(creation_date, list):
            creation_date = creation_date[0]

        if isinstance(creation_date, str):
            # String olarak geliyorsa, dateutil.parser ile datetime objesine dönüştürüyoruz
            creation_date = parser.parse(creation_date)

        # creation_date bir datetime objesi ise, yaş hesaplıyoruz
        if isinstance(creation_date, datetime):
            current_date = datetime.now()
            domain_age = current_date.year - creation_date.year
            print(f"Domain Age: {domain_age} years")
            return domain_age

        else:
            print("Creation date is not available or not in expected format.")
            return None  # Hatalı durumda None döndürüyoruz

    except Exception as e:
        print(f"Error: {e}")
        return None  # Hata durumunda None döndürüyoruz

        # Eğer creation_date datetime objesi ise, tzinfo'yu temizliyoruz
        #if isinstance(creation_date, datetime):
         #   creation_date = creation_date.replace(tzinfo=None)

        # Eğer creation_date string formatında ise, date objesine dönüştürüyoruz
        #elif isinstance(creation_date, str):
         #   try:
          #      creation_date = datetime.strptime(creation_date.split(' ')[0], "%Y-%m-%d")
           # except ValueError:
            #    raise ValueError("Creation date formatı yanlış.")

        # Eğer creation_date geçerliyse, domain yaşını hesaplıyoruz
        #if creation_date:

        #else:
         #   raise ValueError("Creation date bulunamadı.")

    except Exception as e:
        print(f"Domain yaşını alırken hata: {e}")
        return None  # Hata durumunda None döndürüyoruz

def get_last_updated_date(url):
    try:
        url = ensure_url_scheme(url)

        response = requests.get(url,timeout=15)
        response.raise_for_status()
        content = decode_response_content(response)


        soup = BeautifulSoup(response.content.decode('utf-8', 'ignore'), "html.parser")

        # Meta tag ile kontrol
        last_modified_meta = soup.find('meta', {'name': 'last-modified'})
        if last_modified_meta and 'content' in last_modified_meta.attrs:
            date_str = last_modified_meta['content']
            date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S')
            return {"year": date.year, "month": date.month}

        # meta property kontrolü
        og_updated_time_meta = soup.find('meta', {'property': 'og:updated_time'})
        if og_updated_time_meta and 'content' in og_updated_time_meta.attrs:
            date_str = og_updated_time_meta['content']
            date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S')
            return {"year": date.year, "month": date.month}

        # Sayfa metninden kontrol
        possible_texts = ["son güncelleme", "last updated", "last modified", "güncellendi"]
        for text in possible_texts:
            found_text = soup.find(string=re.compile(text, re.IGNORECASE))
            if found_text:
                date_match = re.search(r'\b\d{4}-\d{2}-\d{2}\b', found_text)
                if date_match:
                    date_str = date_match.group()
                    date = datetime.strptime(date_str, '%Y-%m-%d')
                    return {"year": date.year, "month": date.month}

        # JavaScript'teki tarih kontrolü
        script_tags = soup.find_all('script')
        date_pattern = re.compile(r'\b(\d{4})-(\d{2})-\d{2}|\b(\d{2})/(\d{2})/(\d{4})\b')

        for script in script_tags:
            if script.string and date_pattern.search(script.string):
                match = date_pattern.search(script.string)
                if match:
                    if match.group(1) and match.group(2):  # YYYY-MM-DD formatı
                        year, month = int(match.group(1)), int(match.group(2))
                    elif match.group(5) and match.group(4):  # MM/DD/YYYY formatı
                        year, month = int(match.group(5)), int(match.group(4))
                    return {"year": year, "month": month}

        #header'dan kontrol
        if 'Last-Modified' in response.headers:
            date_str = response.headers['Last-Modified']
            date = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %Z')
            return {"year": date.year, "month": date.month}

        #Sitemap kontrolü
        sitemap_url = url.rstrip('/') + "/sitemap.xml"
        sitemap_response = requests.get(sitemap_url, timeout=10)
        if sitemap_response.status_code == 200:
            sitemap_soup = BeautifulSoup(sitemap_response.content, 'xml')
            lastmod_tag = sitemap_soup.find('lastmod')
            if lastmod_tag:
                date_str = lastmod_tag.text.strip()
                date = datetime.strptime(date_str, '%Y-%m-%d')
                return {"year": date.year, "month": date.month}

        return {"year": None, "month": None}

    except requests.exceptions.RequestException as e:
        print(f"Error fetching last updated date for {url}: {e}")
        return {"year": None, "month": None}


with open('veriler2.json', 'r', encoding='utf-8') as file:
    veriler = json.load(file)

#kuyruk = deque((data["_id"], data["url"]) for data in veriler)

not_found_urls = []
whois_error_urls = []
cookies = [
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

def tag_website(_id,url):

    if not url.startswith('http'):
        url = 'http://' + url

    scraper = cloudscraper.create_scraper()

    retry_attempts = 5  # Zaman aşımı hatalarındaki deneme sayısı

    selected_cookie = random.choice(cookies)
    cookie_data = {selected_cookie["name"]: selected_cookie["value"]}

    headers = {
        'User-Agent': random.choice([
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:90.0) Gecko/20100101 Firefox/90.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edge/91.0.864.59"
        ]),
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive'
    }

    for attempt in range(retry_attempts):
        try:
            start_time = time.time()
            response = scraper.get(url, timeout=15 + min(attempt * 5, 30), cookies=cookie_data, headers=headers)
            response.raise_for_status()
            load_time = time.time() - start_time

            # Cloudflare delay
            if "Attention" in response.text or "Just a moment" in response.text or "Checking your browser" in response.text:
                print(f"Cloudflare koruması ile karşılaşıldı, {url} için bekleniyor")
                time.sleep(1800)




            soup = BeautifulSoup(response.content.decode('utf-8', 'ignore'), "html.parser")
            # H , TİTLE, META
            # h1, h2, h3 etiketleri, title ve meta description'ı al
            h1_tags = [clean_text(h1.get_text().strip()) for h1 in soup.find_all('h1')]
            h2_tags = [clean_text(h2.get_text().strip()) for h2 in soup.find_all('h2')]
            h3_tags = [clean_text(h3.get_text().strip()) for h3 in soup.find_all('h3')]

            title_tag = ""
            if soup.title:
                title_tag = clean_text(soup.title.string.strip()) if soup.title.string else ""

            meta_desc = soup.find("meta", attrs={"name": "description"})
            meta_description = clean_text(
                meta_desc["content"].strip()) if meta_desc and "content" in meta_desc.attrs else ""

            # SSL KONTROLÜ
            ssl_var_mi = has_ssl_certificate(url)

            #SON GÜNCELLENME TARİHİ

            last_updated = get_last_updated_date(url)
            last_update_year = last_updated["year"]
            last_update_month = last_updated["month"]

            #MOBİL UYUMLULUK
            mobile_compatibility = bool(soup.find('meta', attrs={'name': 'viewport'}))

            #DOMAIN AGE
            domain_age = get_site_age(url)

            # Sayfa içeriğinden 300 karakterlik rastgele bir kısım al
            content = soup.get_text(strip=True)
            random_content = get_random_content(content, length=300)

            strong_tags = soup.find_all("strong")
            underline_tags = soup.find_all("u")
            strong_texts = [tag.get_text(strip=True) for tag in strong_tags] if strong_tags else []
            underline_texts = [tag.get_text(strip=True) for tag in underline_tags] if underline_tags else []

            return {
                "_id": _id,
                "url": url,
                "h1_keyword": h1_tags,
                "h2_keyword": h2_tags,
                "h3_keyword": h3_tags,
                "title_keyword": title_tag,
                "meta_keyword": meta_description,
                "load_time":round(load_time, 2),
                "last_update_year": last_update_year,
                "last_update_month": last_update_month,
                "mobile_compatibility": mobile_compatibility,
                "ssl_certificate": ssl_var_mi,
                "site_age": domain_age,
                "processed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "random_content": random_content,
                "strong_texts": strong_texts,
                "underline_texts":underline_texts
            }

        except requests.RequestException as e:
            if '404' in str(e):
                not_found_urls.append(url)
            if attempt < retry_attempts - 1:
                wait_time = random.uniform(3, 6)
                print(f"Zaman aşımı hatası aldı, {wait_time} saniye bekliyor ve tekrar deniyor")
                time.sleep(wait_time)
            else:
                print(f"Error fetching {url}: {e}")
                return {
                    "url": url,
                    "ssl_certificate": False,
                    "error": str(e)
                }
        except Exception as e:
            print(f"Beklenmeyen bir hata oluştu {url}: {e}")
            return {
                "url": url,
                "ssl_certificate": False,
                "error": str(e)
            }


# URL'leri paralel işleme
def process_with_delay(args):
    _id, url = args
    time.sleep(5)
    result = tag_website(_id, url)
    return result

dynamic_thread_count = get_dynamic_thread_count()
print(f"Kullanılan iş parçacığı sayısı: {dynamic_thread_count}")

with ThreadPoolExecutor(max_workers=dynamic_thread_count) as executor:
    results = list(executor.map(process_with_delay, [(veri['_id'], veri['url']) for veri in veriler]))






# Geçerli sonuçlar
sonuclar = [result for result in results if result and "error" not in result]



# JSON dosyalarına yazma
with open('not_found_urls.json', 'w', encoding='utf-8') as nf_file:
    json.dump(not_found_urls, nf_file, ensure_ascii=False, indent=4)

with open('whois_error_urls.json', 'w', encoding='utf-8') as we_file:
    json.dump(whois_error_urls, we_file, ensure_ascii=False, indent=4)

with open('sonuclar2.json', 'w', encoding='utf-8') as output_file:
    json.dump(sonuclar, output_file, ensure_ascii=False, indent=4)

print("Sonuçlar 'sonuclar.json' dosyasına kaydedildi.")
print("404 hatası veren URL'ler 'not_found_urls.json' dosyasına kaydedildi.")
print("Whois hatası veren URL'ler 'whois_error_urls.json' dosyasına kaydedildi.")