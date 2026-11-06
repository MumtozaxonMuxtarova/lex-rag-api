import json
from pathlib import Path
import pytest
from app.engine import Engine
from app.models import Item, Options

@pytest.fixture(scope='module')
def engine():
    if not Path('data/lex.jsonl').exists():
        pytest.skip('Download the official corpus first')
    return Engine('data/lex.jsonl')

def test_explicit_article_stays_in_requested_code(engine):
    result = engine.answer(Item(id='q', question='Mehnat kodeksining 33-moddasida nima belgilangan?', language='uz-Latn'), Options(as_of_date='2026-11-06'))
    assert result['contexts'][0]['doc_id'] == 'lex:6257288'
    assert result['contexts'][0]['article'] == '33-modda'

def test_generic_query_words_cannot_answer_sports_question(engine):
    result = engine.answer(Item(id='q', question='Futbol bo‘yicha jahon chempioni kim?', language='uz-Latn'), Options(as_of_date='2026-11-06'))
    assert result['status'] == 'no_answer'

def test_evaluation_gold_quotes_are_from_actual_chunks(engine):
    dataset = json.loads(Path('evaluation/questions.json').read_text(encoding='utf-8'))
    chunks = {c['chunk_id']: c for c in engine.chunks}
    assert len(dataset['questions']) == 100
    for q in dataset['questions']:
        assert q['answerable'] == bool(q['expected_sources'])
        for s in q['expected_sources']:
            assert s['quote'] in chunks[s['chunk_id']]['text']
