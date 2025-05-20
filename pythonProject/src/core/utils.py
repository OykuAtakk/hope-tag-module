import re
from urllib.parse import urlparse


def ensure_url_scheme(url):
    return url if url.startswith(('http://', 'https://')) else 'http://' + url

def clean_text(text):

    text = re.sub(r"(\w+)' (\w+)", r"\1, \2", text)
    text = re.sub(r"'[^ ]*", "", text)
    text = re.sub(r"[^a-zA-Z0-9çÇğĞıİöÖşŞüÜ ]", "", text)
    return ",".join(text.split()).strip()