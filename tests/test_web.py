import pytest
from fastapi.testclient import TestClient
from app.coverage import describe_corpus
from app.main import create_app

KEY = 'web-interface-test-secret'

@pytest.fixture
def web_client(tmp_path):
    with TestClient(create_app(tmp_path/'db.sqlite3', tmp_path/'missing', api_key=KEY, rate_interval=0)) as client:
        yield client

def test_interface_assets_and_no_embedded_secret(web_client):
    response = web_client.get('/')
    assert response.status_code == 200
    assert 'text/html' in response.headers['content-type']
    assert 'frame-ancestors' in response.headers['content-security-policy']
    assert KEY not in response.text
    for asset, mime in [('app.js', 'javascript'), ('style.css', 'text/css')]:
        asset_response = web_client.get('/assets/' + asset)
        assert asset_response.status_code == 200
        assert mime in asset_response.headers['content-type']
        assert KEY not in asset_response.text
    assert web_client.get('/assets/%2e%2e/main.py').status_code == 404

@pytest.mark.parametrize('path', ['/v1/meta', '/v1/coverage', '/v1/rag/batch/missing'])
def test_interface_does_not_bypass_api_auth(web_client, path):
    assert web_client.get(path).status_code == 401
    assert web_client.post('/v1/rag/batch', json={}).status_code == 401

def test_empty_corpus_is_reported_without_fabricated_counts(web_client):
    response = web_client.get('/v1/coverage', headers={'Authorization': f'Bearer {KEY}'})
    assert response.status_code == 200
    body = response.json()
    assert body['total_chunks'] == body['document_variants'] == 0
    assert body['date_windows'] == {}
    assert body['snapshot_date'] is None

def test_coverage_uses_intersection_of_available_editions():
    rows = [dict(doc_id='lex:1', language='uz-Latn', doc_title='First', valid_from='2026-09-12', snapshot_date='2026-11-06', url='https://lex.uz/docs/1', edition_date='2026-09-12'),
            dict(doc_id='lex:2', language='uz-Latn', doc_title='Second', valid_from='2026-10-15', snapshot_date='2026-11-06', url='https://lex.uz/docs/2', edition_date='2026-10-15')]
    coverage = describe_corpus(rows)
    assert coverage['date_windows']['uz-Latn'] == {'from': '2026-10-15', 'to': '2026-11-06'}
    assert coverage['total_chunks'] == 2
