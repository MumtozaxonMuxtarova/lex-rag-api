"""Freeze source-derived test answers, including ten genuinely changed norms.

Run after history ingestion. This authoring tool is separate from retrieval and is
never imported by the API. Do not regenerate a dataset when comparing runs.
"""
import hashlib
import json
from pathlib import Path

from app.retrieval import best_passage


def prepare():
    path = Path('data/lex.jsonl')
    chunks = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    latest = {}
    historical = {}
    for c in chunks:
        key = (c['doc_id'], c['language'], c['article'])
        if c['valid_from'] <= '2026-11-06' < (c['valid_to'] or '9999-12-31'):
            latest[key] = c
        if c['valid_from'] <= '2025-01-01' < (c['valid_to'] or '9999-12-31'):
            historical[key] = c
    changed = [(latest[k], historical[k]) for k in sorted(latest)
               if k[1] == 'uz-Latn' and k in historical
               and best_passage(latest[k], '') != best_passage(historical[k], '')]
    chosen = []
    for doc in sorted({c['doc_id'] for c, _ in changed}):
        chosen.extend([(c, old) for c, old in changed if c['doc_id'] == doc][:5])
    if len(chosen) != 10:
        raise ValueError('Ten verified changed norms are required')
    dataset = json.loads(Path('evaluation/questions-original.json').read_text(encoding='utf-8'))
    changes = iter(chosen)
    for q in dataset['questions']:
        if q['category'] == 'tahrir':
            current, previous = next(changes)
            heading = current['heading'].split('. ', 1)[-1]
            q.update(question=f'2026-11-06 holatiga {heading} qanday tartibga solinadi?',
                     language='uz-Latn', expected_doc_id=current['doc_id'], expected_article=current['article'],
                     expected_sources=[{k: current[k] for k in ('doc_id', 'article', 'chunk_id', 'edition_date')}],
                     historical_evidence={'as_of_date': '2025-01-01', 'chunk_id': previous['chunk_id'],
                                          'edition_date': previous['edition_date'],
                                          'quote': best_passage(previous, '')},
                     note='Official 2025 and 2026 edition texts differ; the expected answer uses the requested 2026 edition.')
            q['expected_sources'][0]['quote'] = best_passage(current, '')
        q['expected_answer'] = '\n\n'.join(s['quote'] for s in q['expected_sources']) if q['answerable'] else None
    dataset.update(corpus_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), as_of_date='2026-11-06',
                   provenance='Source-derived development dataset. Historical questions compare two verified official editions. Not an independent or hidden benchmark.')
    Path('evaluation/questions.json').write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Frozen 100 questions, including 10 changed-norm cases.')


if __name__ == '__main__':
    prepare()
