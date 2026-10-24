
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
    "Referer": "https://www.espn.com/",
    "Origin": "https://www.espn.com"
}

def get_json(url: str, timeout: int = 4):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if r.status_code == 200:
            return r.json()
        else:
            print(f"[http_client] {url} -> {r.status_code}")
            return None
    except Exception as e:
        print(f"[http_client] error {url}: {e}")
        return None
