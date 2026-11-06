"""Small, transparent integration check, not the independent 100-question evaluation."""
import json
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient
from app.main import create_app

CASES = [
    ('uz-Latn', "Yillik asosiy mehnat ta'tilining eng kam muddati qancha?", 'lex:6257288', '217-modda'),
    ('uz-Cyrl', 'Ҳар йилги асосий энг кам меҳнат таътилининг давомийлиги қанча?', 'lex:6257288', '217-modda'),
    ('ru', 'Какова минимальная продолжительность ежегодного основного трудового отпуска?', 'lex:6257291', 'Статья 217'),
    ('uz-Latn', 'Umumiy daʼvo muddati qancha?', 'lex:111189', '150-modda'),
    ('uz-Cyrl', 'Умумий даъво муддати қанча?', 'lex:111189', '150-modda'),
    ('ru', 'Какой срок исковой давности установлен Гражданским кодексом?', 'lex:111181', 'Статья 150'),
    ('uz-Latn', 'Marsga sayohat chiptasi qancha turadi?', None, None),
]

def run(output='reports/smoke.json'):
    manifest = json.loads(Path('data/lex.manifest.json').read_text(encoding='utf-8'))
    snapshot = manifest['snapshot_date']
    # Expected answers and sources remain client-side and are never sent to the API.
    request = {'run_id': 'real-corpus-smoke', 'batch_id': 'smoke-b01', 'batch_index': 1, 'total_batches': 1,
               'options': {'as_of_date': snapshot, 'return_debug': True},
               'items': [{'id': f'q{i:03}', 'question': question, 'language': language} for i, (language, question, _, _) in enumerate(CASES, 1)]}
    with tempfile.TemporaryDirectory() as tmp:
        with TestClient(create_app(Path(tmp)/'db.sqlite3', 'data/lex.jsonl', api_key='local-smoke-test-secret', rate_interval=0)) as client:
            response = client.post('/v1/rag/batch', json=request, headers={'Authorization': 'Bearer local-smoke-test-secret'})
            response.raise_for_status()
            body = response.json()
    checks = []
    for result, (_, question, doc, article) in zip(body['results'], CASES, strict=True):
        citation = result['citations'][0] if result['citations'] else None
        passed = result['status'] == 'no_answer' if doc is None else result['status'] == 'ok' and citation['doc_id'] == doc and citation['article'] == article
        checks.append({'id': result['id'], 'question': question, 'expected_doc_id': doc, 'expected_article': article, 'passed': passed})
    report = {'kind': 'development smoke check; not a held-out benchmark', 'snapshot_date': snapshot,
              'total': len(checks), 'passed': sum(c['passed'] for c in checks), 'checks': checks, 'response': body}
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Smoke: {report['passed']}/{report['total']}; {output}")
    return report

if __name__ == '__main__':
    report = run()
    raise SystemExit(0 if report['passed'] == report['total'] else 1)
