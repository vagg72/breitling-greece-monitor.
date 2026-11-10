"""Collect publicly indexed Breitling mentions from Google News RSS.
No scraping of private or authenticated social media content.
"""
import datetime as dt
import email.utils
import hashlib
import json
import pathlib
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEST = ROOT / 'data' / 'feed.json'
QUERIES = [
    'Breitling Ελλάδα', 'Breitling Athens', 'Breitling Greece',
    'Breitling Navitimer Ελλάδα', 'Breitling Chronomat Ελλάδα',
    'Breitling service Ελλάδα', 'Breitling site:youtube.com Ελλάδα',
    'Breitling site:reddit.com Greece', 'Breitling site:instagram.com Ελλάδα',
    'Breitling site:facebook.com Ελλάδα',
]

def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')

def fetch(query):
    params = urllib.parse.urlencode({'q':query, 'hl':'el', 'gl':'GR', 'ceid':'GR:el'})
    req = urllib.request.Request('https://news.google.com/rss/search?' + params,
                                 headers={'User-Agent':'BreitlingGreeceMonitor/2.0 (+public RSS)'})
    with urllib.request.urlopen(req, timeout=25) as response:
        return ET.fromstring(response.read(3_000_000))

def parse_date(raw):
    try:
        return email.utils.parsedate_to_datetime(raw).astimezone(dt.timezone.utc).isoformat()
    except (ValueError, TypeError, IndexError):
        return utc_now()

def main():
    old = {}
    if DEST.exists():
        try:
            old = json.loads(DEST.read_text(encoding='utf-8'))
        except (ValueError, OSError):
            pass
    by_id = {i['id']: i for i in old.get('items', []) if isinstance(i,dict) and i.get('id')}
    errors = []
    successes = 0
    for q in QUERIES:
        try:
            root = fetch(q)
            successes += 1
            for item in root.findall('.//channel/item'):
                title = (item.findtext('title') or '').strip()
                link = (item.findtext('link') or '').strip()
                if not title or not link or not link.startswith('https://'):
                    continue
                uid = hashlib.sha256(link.encode('utf-8')).hexdigest()[:24]
                source = item.findtext('source') or 'Google News'
                by_id[uid] = {'id':uid,'title':title,'link':link,
                              'date':parse_date(item.findtext('pubDate')),
                              'source':source}
        except Exception as e:
            errors.append(f'{q}: {type(e).__name__}')
    if successes == 0:
        raise RuntimeError('All sources failed; preserving previous feed')
    items = sorted(by_id.values(), key=lambda i:i.get('date',''), reverse=True)[:500]
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps({'version':2,'updated_at':utc_now(),'queries':len(QUERIES),
                                'successful_queries':successes,'errors':errors,'items':items},
                               ensure_ascii=False, indent=2) + '\n',encoding='utf-8')
    print(f'Saved {len(items)} items, {successes}/{len(QUERIES)} queries successful')

if __name__ == '__main__':
    main()
