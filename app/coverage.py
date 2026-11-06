"""Describe the loaded corpus; counts come from the actual index."""
from collections import defaultdict
from datetime import date, timedelta


def merge_intervals(intervals):
    merged = []
    for start, end in sorted(set(intervals)):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged

def describe_corpus(chunks):
    groups = defaultdict(list)
    for chunk in chunks:
        groups[(chunk['doc_id'], chunk['language'])].append(chunk)
    documents = []
    for (doc_id, language), rows in sorted(groups.items()):
        latest = max(c['edition_date'] for c in rows)
        current_rows = [c for c in rows if c['edition_date'] == latest]
        first = current_rows[0]
        documents.append({
            'doc_id': doc_id, 'title': first['doc_title'], 'language': language,
            'articles': len(current_rows), 'edition_date': first['edition_date'],
            'editions': sorted({c['edition_date'] for c in rows}),
            'indexed_chunks': len(rows),
            'snapshot_date': first['snapshot_date'],
            'url': first.get('source_url', first['url']),
        })
    windows, date_intervals = {}, {}
    for language in sorted({c['language'] for c in chunks}):
        rows = [c for c in chunks if c['language'] == language]
        per_doc = defaultdict(list)
        for c in rows:
            end = (date.fromisoformat(c['snapshot_date']) + timedelta(days=1)).isoformat()
            per_doc[c['doc_id']].append((c['valid_from'], min(c.get('valid_to') or end, end)))
        intersection = None
        for intervals in per_doc.values():
            intervals = merge_intervals(intervals)
            intersection = intervals if intersection is None else merge_intervals(
                (max(a, c), min(b, d)) for a, b in intersection for c, d in intervals if max(a, c) < min(b, d))
        date_intervals[language] = [{'from': a, 'to': (date.fromisoformat(b) - timedelta(days=1)).isoformat()} for a, b in intersection or []]
        if date_intervals[language]:
            # The simple UI date input uses the latest continuous coverage window.
            windows[language] = date_intervals[language][-1]
    return {'total_chunks': len(chunks), 'document_variants': len(documents),
            'documents': documents, 'date_windows': windows, 'date_intervals': date_intervals,
            'snapshot_date': min((c['snapshot_date'] for c in chunks), default=None),
            'scope_note': 'Faqat Mehnat kodeksi va Fuqarolik kodeksining birinchi qismi. Butun lex.uz bazasi emas.',
            'answer_mode': 'Bir yoki bir nechta manbadan aynan olingan matn; har bir iqtibos alohida havola bilan.'}
