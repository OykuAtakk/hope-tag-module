import json
import random
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from config.settings import USER_AGENTS
from core.utils import ensure_url_scheme

def parse_date(date_str):
    date_formats = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%m/%d/%Y",
        "%B %d, %Y",
        "%d %B %Y",
        "%a, %d %b %Y %H:%M:%S %Z"
    ]
    for fmt in date_formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def get_last_updated_date(url, response=None, soup=None):
    url = ensure_url_scheme(url)
    headers = {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive'
    }

    if response is None:
        try:
            response = requests.get(url, timeout=15, headers=headers)
            print(f"HTTP Response for {url}: {response.status_code}")
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching last updated date for {url}: {e}")
            return {"year": None, "month": None}

    if soup is None:
        try:
            soup = BeautifulSoup(response.content.decode('utf-8', 'ignore'), "html.parser")
        except Exception as e:
            print(f"Error creating soup for {url}: {e}")
            return {"year": None, "month": None}

    #time etiketlerinden tarih arama
    time_elements = soup.find_all('time')
    for time_el in time_elements:
        if time_el.has_attr('datetime'):
            date = parse_date(time_el['datetime'])
            if date:
                return {"year": date.year, "month": date.month}

    #Microdata / RDFa kontrolüyle
    for itemprop in ['dateModified', 'datePublished']:
        element = soup.find(attrs={"itemprop": itemprop})
        if element:
            date_str = element.get("content") or element.get_text()
            date = parse_date(date_str)
            if date:
                return {"year": date.year, "month": date.month}

    #meta etiketlerinden tarih arama
    meta_tags = [
        {'name': 'last-modified'},
        {'property': 'og:updated_time'},
        {'property': 'article:modified_time'},
        {'name': 'datePublished'},
        {'name': 'dateModified'},
        {'name': 'revised'},
        {'name': 'guncellenme_tarihi'},
        {'name': 'olusturulma_tarihi'},
        {'name': 'yayimlanma_tarihi'},
        {'name': 'published_time'},
        {'name': 'modified_time'},
        {'property': 'og:published_time'},
        {'name': 'son_guncelleme'},
        {'name': 'haber_guncellenme'},
        {'name': 'dc.date.modified'},
        {'name': 'dc.date.created'},
        {'name': 'article:published_time'},
        {'name': 'lastupdate'},
        {'name': 'revision_date'},
        {'name': 'son_duzenleme_tarihi'}
    ]

    dates = []
    for meta_tag in meta_tags:
        meta_element = soup.find('meta', meta_tag)
        if meta_element and 'content' in meta_element.attrs:
            date_str = meta_element['content']
            date = parse_date(date_str)
            if date:
                dates.append(date)

    #JSON-LD içinde tarih arama
    json_ld_scripts = soup.find_all("script", type="application/ld+json")
    for script in json_ld_scripts:
        try:
            data = json.loads(script.string)
            if isinstance(data, dict):
                for key in ["dateModified", "datePublished"]:
                    if key in data:
                        date = parse_date(data[key])
                        if date:
                            dates.append(date)
        except json.JSONDecodeError:
            continue

    #sayfa metninde arama
    possible_texts = ["son güncelleme", "last updated", "last modified", "güncellendi"]
    for text in possible_texts:
        found_text = soup.find(string=re.compile(text, re.IGNORECASE))
        if found_text:
            date_match = re.search(r'\b(\d{1,2}[./-]\d{1,2}[./-]\d{4})\b', found_text)
            if date_match:
                date_str = date_match.group(1)
                date = parse_date(date_str)
                if date:
                    dates.append(date)

    #script etiketleri içinde arama
    script_tags = soup.find_all('script')
    date_pattern = re.compile(r'\b(\d{1,2}[./-]\d{1,2}[./-]\d{4})\b')
    for script in script_tags:
        if script.string:
            for match in date_pattern.findall(script.string):
                date = parse_date(match)
                if date:
                    dates.append(date)

    #HTTP Headers'dan Last-Modified kontrolü
    if 'Last-Modified' in response.headers:
        date = parse_date(response.headers['Last-Modified'])
        if date:
            dates.append(date)

    #sitemap.xml den tarih kontrolü
    try:
        sitemap_url = url.rstrip('/') + "/sitemap.xml"
        sitemap_response = requests.get(sitemap_url, timeout=10)
        if sitemap_response.status_code == 200:
            sitemap_soup = BeautifulSoup(sitemap_response.content, 'xml')
            lastmod_tag = sitemap_soup.find('lastmod')
            if lastmod_tag:
                date = parse_date(lastmod_tag.text.strip())
                if date:
                    dates.append(date)
    except requests.exceptions.RequestException as e:
        print(f"Error fetching sitemap for {url}: {e}")

    # En güncel tarih seçimi
    if dates:
        latest_date = max(dates)
        return {"year": latest_date.year, "month": latest_date.month}

    return {"year": None, "month": None}