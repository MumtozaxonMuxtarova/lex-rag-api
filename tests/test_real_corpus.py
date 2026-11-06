from pathlib import Path
import pytest
from app.smoke import run

@pytest.mark.skipif(not Path('data/lex.jsonl').exists(), reason='Run app.ingest to download the official corpus')
def test_real_corpus_api(tmp_path):
    report = run(str(tmp_path / 'smoke.json'))
    assert report['passed'] == report['total']
    for result in report['response']['results']:
        for citation in result['citations']:
            context = next(c for c in result['contexts'] if c['chunk_id'] == citation['chunk_id'])
            assert citation['quote'] in context['text']

@pytest.mark.skipif(not Path('data/lex.jsonl').exists(), reason='Official corpus not downloaded')
def test_real_corpus_future_date_is_not_no_answer():
    from app.engine import Engine
    from app.models import Item, Options
    engine = Engine('data/lex.jsonl')
    result = engine.answer(Item(id='q', question='mehnat taʼtili', language='uz-Latn'), Options(as_of_date='2030-01-01'))
    assert result['status'] == 'error'
    assert result['error']['code'] == 'SNAPSHOT_DATE_UNAVAILABLE'
