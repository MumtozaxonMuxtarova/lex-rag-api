"""Verify the published corpus against every retained official source file."""
import hashlib
import json
from collections import Counter
from pathlib import Path

from app.coverage import describe_corpus
from app.engine import Engine


def verify(corpus='data/lex.jsonl', raw_dir='data/raw'):
    path = Path(corpus)
    manifest = json.loads(path.with_suffix('.manifest.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest['corpus_sha256'], 'Corpus digest mismatch'
    engine = Engine(path)
    assert len(engine.chunks) == manifest['total_chunks'], 'Chunk count mismatch'
    sources = {}
    for doc in manifest['documents']:
        raw = (Path(raw_dir) / doc['raw_file']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == doc['source_sha256'], f"Source digest mismatch: {doc['raw_file']}"
        key = doc['doc_id'], doc['language'], doc['edition_date']
        assert key not in sources, 'Duplicate manifest edition'
        sources[key] = doc
    counts = Counter()
    for c in engine.chunks:
        key = c['doc_id'], c['language'], c['edition_date']
        assert c['source_sha256'] == sources[key]['source_sha256'], 'Chunk provenance mismatch'
        assert c['source_url'] == sources[key]['source_url'], 'Source URL mismatch'
        counts[key] += 1
    assert all(counts[k] == doc['articles'] for k, doc in sources.items()), 'Edition article count mismatch'
    report = {'verified': True, 'raw_sources': len(sources), 'chunks': len(engine.chunks),
              'corpus_sha256': manifest['corpus_sha256'], 'coverage': describe_corpus(engine.chunks)}
    Path('reports/corpus-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'coverage'}, indent=2))
    return report


if __name__ == '__main__':
    verify()
