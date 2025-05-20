import os
import requests
import random
import time
import json
import re
import ssl
import socket
import multiprocessing
from datetime import datetime, timedelta
from urllib.parse import urlparse, urljoin
import cloudscraper
from bs4 import BeautifulSoup
import whois
from dateutil import parser
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from requests.cookies import RequestsCookieJar
from src.core.delays import delay_request
from src.core.utils import clean_text, ensure_url_scheme
from src.storage.mongo_context import MongoDbContext
from queue import Queue
from concurrent.futures import ThreadPoolExecutor
from src.classifier.site_classifier import classify_site
from logger import setup_logger
from src.config.settings import SLEEP_DELAY, RETRY_ATTEMPTS, USER_AGENTS, COOKIES


logger = setup_logger()
"""
"""
def load_environment_variables():
    load_dotenv()
    print("[LOG] Çevresel değişkenler yükleniyor...")

    MONGO_URI = os.getenv("MONGO_URI")
    MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")
    PROCESSED_SPIDER_COLL = os.getenv("PROCESSED_COLLECTION_SPIDER")
    PROCESSED_SITES_SEO = os.getenv("PROCESSED_SITES_SEO")
    PROCESSED_SITES_SEO_LINKS = os.getenv("PROCESSED_SITES_SEO_LINKS")
    UNPROCESSABLE_SITES = os.getenv("UNPROCESSABLE_SITES")

    print(f"[LOG] MongoDB bağlanıyor: {MONGO_URI}, Veritabanı: {MONGO_DB_NAME}")

    return MONGO_URI, MONGO_DB_NAME, PROCESSED_SPIDER_COLL, PROCESSED_SITES_SEO, PROCESSED_SITES_SEO_LINKS,UNPROCESSABLE_SITES

def get_new_records(mongo_db_context, collection, one_week_ago):
    """MongoDB'den bir haftadan eski kayıtları alır."""
    query = {
        "$or": [
            {"last_processed_time": {"$exists": False}},
            {"last_processed_time": {"$lt": one_week_ago}}
        ]
    }
    new_records = mongo_db_context.get_datas_from_mongodb(collection, query=query, limit=50)
    return new_records


def get_unprocessable_records(mongo_db_context, collection, twelwe_hours_ago):
    """12 saatten eski işlenemeyen kayıtları alır."""
    query = {
        "processed_time": {"$lt": twelwe_hours_ago.strftime("%Y-%m-%d %H:%M:%S")}
    }
    return mongo_db_context.get_datas_from_mongodb(collection, query=query, limit=50)




def save_results(mongo_db_context, batch_results, PROCESSED_SITES_SEO, PROCESSED_SITES_SEO_LINKS,
                 PROCESSED_SPIDER_COLL, unprocessable_results):

    # Başarılı sonuçlar
    for result in batch_results:
        mongo_db_context.save_datas_to_mongo(PROCESSED_SITES_SEO, result)
        print(f"[LOG] URL {result['url']} processed_sites_seo koleksiyonuna kaydedildi.")

        link_record = {
            "url": result["url"],
            "processed_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        mongo_db_context.save_datas_to_mongo(PROCESSED_SITES_SEO_LINKS, link_record)
        print(f"[LOG] URL {result['url']} processed_sites_seo_links koleksiyonuna kaydedildi.")

        mongo_db_context.update_mongo_record(
            PROCESSED_SPIDER_COLL,
            {"_id": result["_id"]},
            {"$set": {"last_processed_time": datetime.now()}}
        )
        print(f"[LOG] kayıt last_processed_time alanı güncellendi.")

    # İşlenemeyen sonuçlar
    for error_result in unprocessable_results:
        mongo_db_context.save_datas_to_mongo("unprocessable_sites", error_result)
        print(f"[LOG] URL {error_result['url']} işlenemeyenler koleksiyonuna kaydedildi.")



from tasks.scheduler import main

if __name__ == "__main__":
    main()
