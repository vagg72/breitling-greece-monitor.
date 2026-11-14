"""Breitling Greece Monitor 2.1: collect and filter publicly indexed news.

Only public Google News RSS results are used; private social content is not accessed.
"""
import datetime as dt
import email.utils
import hashlib
import json
import pathlib
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent
DEST = ROOT / 'feed.json'
QUERIES = [
    '"Breitling" Ελλάδα', '"Breitling" Athens', '"Breitling" Greece',
    '"Breitling" ελληνικά ρολόγια', '"Breitling" boutique Greece',
    '"Breitling" Navitimer', '"Breitling" Chronomat',
    '"Breitling" Superocean', '"Breitling" watch launch',
    '"Breitling" watch news', '"Breitling" partnership',
    '"Breitling" site:instagram.com Greece',
    '"Breitling" site:facebook.com Greece',
    '"Breitling" site:youtube.com',
]

BRAND = re.compile(r'(?<![a-z])breitling(?![a-z])', re.IGNORECASE)
# Model-only mentions are accepted only when they explicitly discuss watches.
MODELS = re.compile(r'\b(navitimer|chronomat|superocean|avenger|premier b01|top time)\b', re.I)
WATCH_CONTEXT = re.compile(r'\b(watch|watches|timepiece|chronograph|wristwatch|ρολόι|ρολόγια|χρονογράφος|ωρολογοποιία)\b', re.I)
GREECE = re.compile(r'\b(greece|greek|athens|thessaloniki|ελλάδα|ελλάδας|ελληνικ|αθήνα|αθήνας|θεσσαλονίκη)\w*', re.I)
SOCIAL_DOMAINS = ('instagram.com', 'facebook.com', 'youtube.com', 'reddit.com', 'tiktok.com', 'x.com')


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')


def fetch(query):
    params = urllib.parse.urlencode({'q': query, 'hl': 'el', 'gl': 'GR', 'ceid': 'GR:el'})
    req = urllib.request.Request('https://news.google.com/rss/search?' + params,
                                 headers={'User-Agent': 'BreitlingGreeceMonitor/2.1 (public RSS)'})
    with urllib.request.urlopen(req, timeout=25) as response:
        return ET.fromstring(response.read(3_000_000))


def parse_date(raw):
    try:
        return email.utils.parsedate_to_datetime(raw).astimezone(dt.timezone.utc).isoformat()
    except (ValueError, TypeError, IndexError):
        return utc_now()


def relevant(title):
    return bool(BRAND.search(title) or (MODELS.search(title) and WATCH_CONTEXT.search(title)))


def classify(title, link):
    host = urllib.parse.urlparse(link).netloc.lower()
    if any(host == d or host.endswith('.' + d) for d in SOCIAL_DOMAINS):
        return 'social'
    return 'greece' if GREECE.search(title) else 'international'


def main():
    old = {}
    if DEST.exists():
        try:
            old = json.loads(DEST.read_text(encoding='utf-8'))
        except (ValueError, OSError):
            pass
    # Re-filter older records: do not re-introduce unrelated stories.
    by_id = {}
    for item in old.get('items', []):
        if not isinstance(item, dict):
            continue
        title, link = item.get('title', ''), item.get('link', '')
        if item.get('id') and relevant(title) and link.startswith('https://'):
            item['category'] = classify(title, link)
            by_id[item['id']] = item

    errors = []
    successes = 0
    for query in QUERIES:
        try:
            root = fetch(query)
            successes += 1
            for item in root.findall('.//channel/item'):
                title = (item.findtext('title') or '').strip()
                link = (item.findtext('link') or '').strip()
                if not title or not link.startswith('https://') or not relevant(title):
                    continue
                uid = hashlib.sha256(link.encode('utf-8')).hexdigest()[:24]
                by_id[uid] = {
                    'id': uid, 'title': title, 'link': link,
                    'date': parse_date(item.findtext('pubDate')),
                    'source': item.findtext('source') or 'Google News',
                    'category': classify(title, link),
                }
        except Exception as exc:
            errors.append(f'{query}: {type(exc).__name__}')
    if successes == 0:
        raise RuntimeError('All sources failed; preserving previous feed')
    items = sorted(by_id.values(), key=lambda x: x.get('date', ''), reverse=True)[:500]
    DEST.write_text(json.dumps({
        'version': '2.1', 'updated_at': utc_now(), 'queries': len(QUERIES),
        'successful_queries': successes, 'errors': errors, 'items': items,
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Saved {len(items)} relevant items, {successes}/{len(QUERIES)} queries successful')


if __name__ == '__main__':
    main()
