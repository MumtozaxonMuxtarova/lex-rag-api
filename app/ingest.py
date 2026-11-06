"""Download date-pinned lex.uz pages and retain article text, not site commentary."""
import argparse
import hashlib
import json
import re
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlencode

import httpx
from bs4 import BeautifulSoup

DATE = re.compile(r'\b(\d{2}\.\d{2}\.\d{4})(?:\s+(\d{2}))?')

def iso(value):
    day, month, year = value.split('.')
    return f'{year}-{month}-{day}'

def element_text(element):
    # The id/name node contains official text. Other siblings are UI buttons.
    node = element.find('div', id=True)
    if node is None:
        raise ValueError('lex.uz text node not found; site structure may have changed')
    for sup in node.find_all('sup'):
        sup.replace_with('^' + sup.get_text())
    return re.sub(r'\s+', ' ', node.get_text('', strip=False)).strip(), node.get('id')

def selected_revision(soup):
    selected = soup.select_one('.lx_date_selected')
    if selected is None:
        raise ValueError('Selected edition is missing')
    match = DATE.search(selected.get_text(' ', strip=True))
    if not match:
        raise ValueError('Cannot parse selected edition')
    return iso(match[1]), match[0]

def available_revisions(soup):
    values = {}
    for node in soup.select('.lx_date_selected, .lx_date_link'):
        if 'ONDATE2' in node.get('onclick', ''):
            continue
        match = DATE.search(node.get_text(' ', strip=True))
        if match:
            values.setdefault(iso(match[1]), match[0])
    return values

def parse_document(html, source, snapshot_date, source_url):
    soup = BeautifulSoup(html, 'html.parser')
    edition, edition_label = selected_revision(soup)
    if edition > snapshot_date:
        raise ValueError('Refusing a future edition')
    root = soup.select_one('#divCont')
    if root is None:
        raise ValueError('Official document container is missing')
    title = re.sub(r'^\s*\d{2}\.\d{2}\.\d{4}\.\s*', '', soup.title.get_text(' ', strip=True)).strip()
    warning = soup.select_one('.act_warning')
    if warning and re.search(r'kuchini yo.qot|кучини йўқот|утратил', warning.get_text().lower()):
        raise ValueError('Repealed document needs explicit historical handling')
    boundary = date.fromisoformat(snapshot_date) + timedelta(days=1)
    later = [date.fromisoformat(d) for d in available_revisions(soup) if d > edition]
    if later:
        boundary = min(boundary, min(later))
    digest = hashlib.sha256(html.encode('utf-8')).hexdigest()
    articles = []
    current = None

    def finish():
        nonlocal current
        if current and current['paragraphs']:
            current['text'] = current['heading'] + '\n' + '\n'.join(current['paragraphs'])
            articles.append(current)
        current = None

    for element in root.find_all('div', recursive=False):
        classes = set(element.get('class', []))
        if 'CLAUSE_DEFAULT' in classes:
            finish()
            heading, anchor = element_text(element)
            if source['language'] == 'ru':
                match = re.match(r'^Статья\s+(\d+(?:\^\d+)?)\.', heading, re.I)
            else:
                word = 'модда' if source['language'] == 'uz-Cyrl' else 'modda'
                match = re.match(r'^(\d+(?:\^\d+)?)-' + word + r'\.', heading, re.I)
            if not match:
                raise ValueError(f'Unknown article heading: {heading[:100]}')
            number = match[1]
            article = f'Статья {number}' if source['language'] == 'ru' else f'{number}-modda'
            current = {
                'chunk_id': f"lex:{abs(source['id'])}#{source['language']}#art-{number}#{edition}",
                'doc_id': f"lex:{abs(source['id'])}", 'doc_title': title, 'doc_type': 'kodeks',
                'url': f"https://lex.uz/docs/{source['id']}", 'article': article,
                'article_number': number, 'part': None, 'heading': heading, 'paragraphs': [],
                'edition_date': edition, 'edition_label': edition_label,
                'valid_from': edition, 'valid_to': boundary.isoformat(),
                'doc_status': 'amalda', 'language': source['language'], 'snapshot_date': snapshot_date,
                'source_url': source_url, 'source_anchor': anchor, 'source_sha256': digest,
            }
        elif classes & {'TEXT_HEADER_DEFAULT', 'ACT_TITLE', 'SIGNATURE', 'PUBLICATION_ORIGIN'}:
            finish()
        elif current and classes & {'ACT_TEXT', 'BY_DEFAULT'}:
            text, _ = element_text(element)
            if text:
                current['paragraphs'].append(text)
    finish()
    if len(articles) < source.get('min_articles', 1):
        raise ValueError(f"Too few articles: {len(articles)}")
    if len({c['chunk_id'] for c in articles}) != len(articles):
        raise ValueError('Duplicate article IDs')
    return articles

def download(client, url):
    for attempt in range(3):
        try:
            response = client.get(url)
            response.raise_for_status()
            if len(response.content) > 25_000_000:
                raise ValueError('Source page is unexpectedly large')
            return response.text
        except (httpx.TransportError, httpx.HTTPStatusError):
            if attempt == 2:
                raise
            time.sleep(attempt + 1)

def ingest(manifest, output, raw_dir, snapshot_date, history_since=None):
    date.fromisoformat(snapshot_date)
    if history_since:
        date.fromisoformat(history_since)
        if history_since > snapshot_date:
            raise ValueError('History start is after snapshot date')
    sources = json.loads(Path(manifest).read_text(encoding='utf-8'))
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    chunks, documents = [], []
    with httpx.Client(timeout=60, follow_redirects=False, headers={'User-Agent': 'LexRAGResearch/0.2 (article indexing)'}) as client:
        for source in sources:
            if not isinstance(source['id'], int):
                raise ValueError('Document IDs must be integers')
            base = f"https://www.lex.uz/docs/{source['id']}"
            html = download(client, base)
            soup = BeautifulSoup(html, 'html.parser')
            revisions = available_revisions(soup)
            eligible = [d for d in revisions if d <= snapshot_date]
            if not eligible:
                raise ValueError(f'No eligible edition: {base}')
            current, _ = selected_revision(soup)
            targets = [max(eligible)]
            if history_since:
                previous = [d for d in eligible if d <= history_since]
                if not previous:
                    raise ValueError(f'No edition covers history start: {base}')
                targets = sorted({max(previous), *(d for d in eligible if d >= history_since)})
            base_html = html
            for target in targets:
                url = base + '?' + urlencode({'ONDATE': revisions[target]})
                filename = f"{source['id']}-{source['language']}-{target}.html"
                cached = raw_dir / filename
                if current == target:
                    html = base_html
                elif cached.exists():
                    html = cached.read_bytes().decode('utf-8')
                else:
                    time.sleep(1)
                    html = download(client, url)
                parsed = parse_document(html, source, snapshot_date, url)
                if parsed[0]['edition_date'] != target:
                    raise ValueError('Server returned a different edition')
                # The complete official revision calendar sets the exclusive end.
                later = [d for d in revisions if d > target]
                boundary = min([ (date.fromisoformat(snapshot_date) + timedelta(days=1)).isoformat(), *later])
                for chunk in parsed:
                    chunk['valid_to'] = min(chunk['valid_to'], boundary)
                cached.write_text(html, encoding='utf-8', newline='')
                chunks.extend(parsed)
                documents.append({'doc_id': parsed[0]['doc_id'], 'title': parsed[0]['doc_title'],
                                  'language': source['language'], 'edition_date': target,
                                  'articles': len(parsed), 'source_url': url,
                                  'source_sha256': parsed[0]['source_sha256'], 'raw_file': filename})
                print(f"{source['language']} {parsed[0]['doc_title']}: {len(parsed)} articles, {target}", flush=True)
            time.sleep(1)
    # Publish only after all sources have passed validation.
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text('\n'.join(json.dumps(c, ensure_ascii=False) for c in chunks) + '\n', encoding='utf-8')
    temporary.replace(path)
    report = {'snapshot_date': snapshot_date, 'history_since': history_since, 'documents': documents, 'total_chunks': len(chunks),
              'corpus_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    path.with_suffix('.manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', default='sources/lex.json')
    parser.add_argument('--output', default='data/lex.jsonl')
    parser.add_argument('--raw-dir', default='data/raw')
    parser.add_argument('--snapshot-date', default=date.today().isoformat())
    parser.add_argument('--history-since', help='Import every official edition from this date')
    args = parser.parse_args()
    ingest(args.manifest, args.output, args.raw_dir, args.snapshot_date, args.history_since)
