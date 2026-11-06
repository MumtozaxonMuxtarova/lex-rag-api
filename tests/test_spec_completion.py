import json

import httpx
import pytest

from app.coverage import describe_corpus
from app.engine import Engine
from app.engine import detect_language
from app.models import Item, Options
from app.runner import submit_and_wait


def test_automatic_cyrillic_language_without_distinctive_uzbek_letters():
    assert detect_language('Битимлар тушунчаси') == 'uz-Cyrl'
    assert detect_language('Дастлабки синов муддати') == 'uz-Cyrl'
    assert detect_language('Каков общий срок исковой давности?') == 'ru'


def historical_engine(tmp_path, gap=False):
    common = dict(doc_id='lex:1', doc_title='Sinov kodeksi', doc_type='test',
                  url='https://lex.uz/docs/1', article='1-modda', article_number='1',
                  part=None, doc_status='amalda', language='uz-Latn',
                  snapshot_date='2026-11-06', source_sha256='a' * 64)
    rows = [dict(common, chunk_id='old', edition_date='2025-01-01', valid_from='2025-01-01',
                 valid_to='2026-01-01', text='Sinov muddati yigirma kun.'),
            dict(common, chunk_id='new', edition_date='2026-02-01' if gap else '2026-01-01',
                 valid_from='2026-02-01' if gap else '2026-01-01', valid_to='2026-11-07',
                 text='Sinov muddati o‘ttiz kun.')]
    path = tmp_path / 'historical.jsonl'
    path.write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in rows), encoding='utf-8')
    return Engine(path)


def test_historical_date_selects_only_the_effective_edition(tmp_path):
    engine = historical_engine(tmp_path)
    question = Item(id='q', question='Sinov muddati qancha?', language='uz-Latn')
    for day, expected in [('2025-12-31', 'old'), ('2026-01-01', 'new')]:
        result = engine.answer(question, Options(as_of_date=day))
        assert result['status'] == 'ok'
        assert {c['chunk_id'] for c in result['contexts']} == {expected}
        assert result['citations'][0]['chunk_id'] == expected
    coverage = describe_corpus(engine.chunks)
    assert coverage['date_windows']['uz-Latn'] == {'from': '2025-01-01', 'to': '2026-11-06'}
    assert coverage['documents'][0]['articles'] == 1
    assert len(coverage['documents'][0]['editions']) == 2


def test_historical_gap_is_not_silently_filled(tmp_path):
    engine = historical_engine(tmp_path, gap=True)
    result = engine.answer(Item(id='q', question='Sinov muddati', language='uz-Latn'), Options(as_of_date='2026-01-15'))
    assert result['error']['code'] == 'SNAPSHOT_DATE_UNAVAILABLE'
    assert len(describe_corpus(engine.chunks)['date_intervals']['uz-Latn']) == 2


def test_runner_retries_same_id_and_polls_through_temporary_failure():
    statuses = iter([503, 202, 503, 202, 200])
    calls = []
    payload = {'batch_id': 'same-id', 'items': [{'id': 'q1'}]}

    def handler(request):
        calls.append(request)
        code = next(statuses)
        body = {'status': 'processing'} if code != 200 else {'status': 'completed', 'results': [{'id': 'q1'}]}
        return httpx.Response(code, json=body)

    with httpx.Client(base_url='http://test', transport=httpx.MockTransport(handler)) as client:
        result = submit_and_wait(client, payload, sleep=lambda _: None)
    assert result['status'] == 'completed'
    posts = [json.loads(r.content) for r in calls if r.method == 'POST']
    assert posts == [payload, payload]
    assert all(r.url.path.endswith('/same-id') for r in calls if r.method == 'GET')


def test_runner_does_not_retry_invalid_requests():
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(400, json={'error': 'invalid'})
    with httpx.Client(base_url='http://test', transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            submit_and_wait(client, {'batch_id': 'bad', 'items': []}, sleep=lambda _: None)
    assert len(calls) == 1


def test_runner_obeys_retry_after_without_extra_service_backoff():
    codes = iter([429, 200])
    sleeps = []
    def handler(request):
        code = next(codes)
        return httpx.Response(code, headers={'Retry-After': '2'}, json={'status': 'completed', 'results': [{'id': 'q1'}]})
    with httpx.Client(base_url='http://test', transport=httpx.MockTransport(handler)) as client:
        result = submit_and_wait(client, {'batch_id': 'b', 'items': [{'id': 'q1'}]}, sleep=sleeps.append)
    assert result['status'] == 'completed' and sleeps == [2]


@pytest.fixture(scope='module')
def official_engine():
    from pathlib import Path
    if not Path('data/lex.jsonl').exists():
        pytest.skip('Official corpus not downloaded')
    return Engine('data/lex.jsonl')


def test_multi_subject_answers_cite_both_actual_sources(official_engine):
    engine = official_engine
    result = engine.answer(Item(id='q', question='Xodimning huquqlari va majburiyatlari qanday?', language='uz-Latn'), Options(as_of_date='2026-11-06', return_contexts=False))
    assert {c['article'] for c in result['citations']} == {'21-modda', '22-modda'}
    assert '[1]' in result['answer'] and '[2]' in result['answer']
    for citation in result['citations']:
        context = next(c for c in result['contexts'] if c['chunk_id'] == citation['chunk_id'])
        assert citation['quote'] in context['text'] and context['used_in_answer']


def test_general_written_form_is_not_replaced_by_simple_written_form(official_engine):
    result = official_engine.answer(Item(id='q', question='Bitimlarning shakli; Bitimning yozma shakli qanday?', language='uz-Latn'), Options(as_of_date='2026-11-06'))
    assert {c['article'] for c in result['citations']} == {'105-modda', '107-modda'}


def test_precise_topic_is_not_padded_with_unrelated_decisions(official_engine):
    result = official_engine.answer(Item(id='q', question='Jamoa shartnomasini tuzish zarurligi to‘g‘risida qaror qabul qilish', language='uz-Latn'), Options(as_of_date='2026-11-06', top_k=5))
    assert result['status'] == 'ok' and result['contexts'][0]['article'] == '66-modda'
    assert all(c['article'] not in {'582-modda', '303-modda', '54-modda'} for c in result['contexts'])


@pytest.mark.parametrize('language', ['uz-Cyrl', 'ru'])
def test_requested_answer_language_uses_official_translation(official_engine, language):
    result = official_engine.answer(Item(id='q', question='Yillik asosiy mehnat taʼtilining eng kam muddati qancha?', language='uz-Latn'), Options(as_of_date='2026-11-06', answer_language=language))
    assert result['status'] == 'ok' and result['answer_language'] == language
    assert result['citations'][0]['doc_id'] == ('lex:6257291' if language == 'ru' else 'lex:6257288')
    assert result['citations'][0]['article'] == ('Статья 217' if language == 'ru' else '217-modda')
    assert result['citations'][0]['quote'] in result['contexts'][0]['text']
    assert any('\u0400' <= c <= '\u04ff' for c in result['answer'])


def test_real_changed_norms_retain_distinct_historical_answers(official_engine):
    dataset = json.loads(__import__('pathlib').Path('evaluation/questions.json').read_text(encoding='utf-8'))
    questions = [q for q in dataset['questions'] if q.get('historical_evidence')]
    if not questions:
        pytest.skip('Historical dataset not prepared')
    assert len(questions) == 10
    for q in questions:
        current = q['expected_sources'][0]
        previous = q['historical_evidence']
        family = 'Mehnat' if current['doc_id'] == 'lex:6257288' else 'Fuqarolik'
        item = Item(id=q['id'], question=f"{family} kodeksining {current['article']} qoidalari", language='uz-Latn')
        for day, source in [('2026-11-06', current), (previous['as_of_date'], previous)]:
            result = official_engine.answer(item, Options(as_of_date=day))
            assert result['status'] == 'ok'
            assert result['citations'][0]['chunk_id'] == source['chunk_id']
            assert source['quote'] in result['answer']
        assert current['quote'] != previous['quote']
