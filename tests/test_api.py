import json
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.engine import Engine

KEY = 'unit-test-secret-key-only'

def request(batch_id='b01', **options):
    return {'run_id': 'test', 'batch_id': batch_id, 'batch_index': 1, 'total_batches': 10,
            'options': options, 'items': [{'id': 'q001', 'question': 'sinov hujjati matni', 'language': 'uz-Latn'}]}

@pytest.fixture
def paths(tmp_path):
    # Synthetic text only: not a legal source and never distributed as real corpus.
    c = {'chunk_id': 'lex:1#art-1#2020', 'doc_id': 'lex:1', 'doc_title': 'Sinov hujjati',
         'doc_type': 'test', 'url': 'https://lex.uz/docs/1', 'article': '1-modda', 'part': '1-qism',
         'edition_date': '2020-01-01', 'valid_from': '2020-01-01', 'valid_to': None,
         'doc_status': 'amalda', 'text': 'Bu faqat sinov hujjati matni.', 'language': 'uz-Latn', 'snapshot_date': '2026-11-01'}
    corpus = tmp_path / 'corpus.jsonl'
    corpus.write_text(json.dumps(c), encoding='utf-8')
    return tmp_path / 'db.sqlite3', corpus

@pytest.fixture
def client(paths):
    with TestClient(create_app(*paths, api_key=KEY, rate_interval=0)) as c:
        c.headers['Authorization'] = f'Bearer {KEY}'
        yield c

def test_auth(client):
    assert client.get('/v1/health', headers={'Authorization': ''}).status_code == 200
    assert client.get('/v1/meta', headers={'Authorization': ''}).status_code == 401

@pytest.mark.parametrize('case', ['empty', 'eleven', 'duplicate', 'blank', 'long', 'language', 'temperature'])
def test_validation(client, case):
    data = request()
    if case == 'empty': data['items'] = []
    if case == 'eleven': data['items'] = [{'id': str(i), 'question': 'a'} for i in range(11)]
    if case == 'duplicate': data['items'] *= 2
    if case == 'blank': data['items'][0]['question'] = '  '
    if case == 'long': data['items'][0]['question'] = 'a' * 2001
    if case == 'language': data['items'][0]['language'] = 'en'
    if case == 'temperature': data['options']['temperature'] = 0.5
    assert client.post('/v1/rag/batch', json=data).status_code == 400

def test_citations_and_idempotency(client):
    data = request(return_contexts=False)
    response = client.post('/v1/rag/batch', json=data)
    assert response.status_code == 200
    result = response.json()
    item = result['results'][0]
    assert item['status'] == 'ok'
    assert item['citations'][0]['quote'] in item['contexts'][0]['text']
    assert item['citations'][0]['chunk_id'] == item['contexts'][0]['chunk_id']
    assert client.post('/v1/rag/batch', json=data).json() == result
    assert client.get('/v1/rag/batch/b01').json() == result
    data['items'][0]['question'] = 'changed'
    assert client.post('/v1/rag/batch', json=data).status_code == 409


def test_custom_seed_roundtrip(client):
    body = request(seed=917)
    assert client.post('/v1/rag/batch', json=body).json()['seed'] == 917
    assert client.get('/v1/rag/batch/b01').json()['seed'] == 917


def test_all_ten_saved_http_batches_echo_seed(client, tmp_path):
    from app.runner import run_batches
    questions = [{'id': f'q{i:03}', 'question': 'sinov hujjati matni'} for i in range(1, 101)]
    run_batches(client, questions, {'seed': 42, 'as_of_date': '2026-11-01'}, 'seed-test', tmp_path)
    for i in range(1, 11):
        saved = json.loads((tmp_path / f'b{i:02}.json').read_bytes())
        assert saved['seed'] == 42 and len(saved['results']) == 10

def test_no_answer_and_date(client):
    data = request(as_of_date='2019-01-01')
    assert client.post('/v1/rag/batch', json=data).json()['results'][0]['status'] == 'no_answer'
    data = request('b02')
    data['items'][0]['question'] = 'unrelated spaceship'
    result = client.post('/v1/rag/batch', json=data).json()['results'][0]
    assert result['no_answer'] and result['citations'] == []

def test_empty_index(tmp_path):
    with TestClient(create_app(tmp_path/'db', tmp_path/'missing', KEY, rate_interval=0)) as client:
        result = client.post('/v1/rag/batch', json=request(), headers={'Authorization': f'Bearer {KEY}'}).json()
        assert result['results'][0]['error']['code'] == 'INDEX_UNAVAILABLE'

def test_rate_limit(paths):
    with TestClient(create_app(*paths, KEY, rate_interval=10)) as client:
        client.headers['Authorization'] = f'Bearer {KEY}'
        assert client.post('/v1/rag/batch', json=request()).status_code == 200
        assert client.post('/v1/rag/batch', json=request()).status_code == 200
        response = client.post('/v1/rag/batch', json=request('b02'))
        assert response.status_code == 429 and response.headers['Retry-After'] == '1'

def test_async_and_failure_isolation(paths, monkeypatch):
    original = Engine.answer
    def slow(self, item, options):
        time.sleep(.03)
        if item.id == 'bad': raise RuntimeError('synthetic failure')
        return original(self, item, options)
    monkeypatch.setattr(Engine, 'answer', slow)
    with TestClient(create_app(*paths, KEY, rate_interval=0, sync_timeout=.001)) as client:
        client.headers['Authorization'] = f'Bearer {KEY}'
        data = request()
        data['items'].append({'id': 'bad', 'question': 'test'})
        assert client.post('/v1/rag/batch', json=data).status_code == 202
        for _ in range(100):
            response = client.get('/v1/rag/batch/b01')
            if response.status_code == 200: break
            time.sleep(.01)
        results = response.json()['results']
        assert [r['status'] for r in results] == ['ok', 'error']

def test_concurrent_retry_processed_once(paths, monkeypatch):
    original = Engine.answer
    calls = []
    def tracked(self, item, options):
        calls.append(item.id)
        time.sleep(.05)
        return original(self, item, options)
    monkeypatch.setattr(Engine, 'answer', tracked)
    with TestClient(create_app(*paths, KEY, rate_interval=0)) as client:
        client.headers['Authorization'] = f'Bearer {KEY}'
        with ThreadPoolExecutor(4) as pool:
            responses = list(pool.map(lambda _: client.post('/v1/rag/batch', json=request()), range(4)))
        assert all(r.status_code in (200, 202) for r in responses)
        assert len(calls) == 1

def test_restart_persistence(paths):
    with TestClient(create_app(*paths, KEY, rate_interval=0)) as client:
        client.headers['Authorization'] = f'Bearer {KEY}'
        result = client.post('/v1/rag/batch', json=request()).json()
    with TestClient(create_app(*paths, KEY, rate_interval=0)) as client:
        client.headers['Authorization'] = f'Bearer {KEY}'
        assert client.get('/v1/rag/batch/b01').json() == result
