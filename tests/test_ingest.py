import pytest
from app.ingest import parse_document, available_revisions
from app.retrieval import tokenize
from bs4 import BeautifulSoup

HTML = '''<html><head><title>28.10.2022. Sinov kodeksi</title></head><body>
<div class="lx_date_selected">15.10.2026 01</div>
<div class="lx_date_link" onclick="open('/docs/1?ONDATE=28.01.2027')">28.01.2027</div>
<div id="divCont">
<div class="ACT_TITLE"><div id="1">Sinov kodeksi</div></div>
<div class="CLAUSE_DEFAULT"><div class="lx_elem2">UI tugmalari</div><div id="2">1-modda. Sarlavha</div></div>
<div class="COMMENTLEXUZ">Tahrir izohi va sharh</div>
<div class="INDEXES_ON_REF">Qidiruv indeksi</div>
<div class="ACT_TEXT"><div class="lx_elem2">Hujjatga taklif yuborish</div><div id="3">Birinchi xatboshi.</div></div>
<div class="BY_DEFAULT"><div id="4">Ikkinchi xatboshi.</div></div>
<div class="TEXT_HEADER_DEFAULT"><div id="5">Yangi bob</div></div>
<div class="ACT_TEXT"><div id="6">Oldingi moddaga kirmasligi kerak.</div></div>
<div class="CLAUSE_DEFAULT"><div id="7">2<sup>1</sup>-modda. Qoʻshimcha</div></div>
<div class="ACT_TEXT"><div id="8">Qoʻshimcha norma.</div></div>
</div></body></html>'''

def test_official_text_only_and_article_boundaries():
    chunks = parse_document(HTML, {'id': -1, 'language': 'uz-Latn'}, '2026-11-06', 'https://www.lex.uz/docs/-1')
    assert len(chunks) == 2
    assert chunks[0]['text'] == '1-modda. Sarlavha\nBirinchi xatboshi.\nIkkinchi xatboshi.'
    assert chunks[0]['part'] is None
    assert chunks[0]['valid_to'] == '2026-11-07'
    assert chunks[1]['article_number'] == '2^1'
    assert chunks[0]['source_anchor'] == '2'
    assert len(chunks[0]['source_sha256']) == 64

def test_future_edition_rejected():
    with pytest.raises(ValueError, match='future'):
        parse_document(HTML, {'id': 1, 'language': 'uz-Latn'}, '2026-10-01', 'https://www.lex.uz/docs/1')

def test_site_structure_change_fails_closed():
    with pytest.raises(ValueError, match='container'):
        parse_document(HTML.replace('divCont', 'unknown'), {'id': 1, 'language': 'uz-Latn'}, '2026-11-06', 'https://www.lex.uz/docs/1')

def test_edition_list_preserves_discriminator():
    assert available_revisions(BeautifulSoup(HTML, 'html.parser'))['2026-10-15'] == '15.10.2026 01'

def test_uzbek_script_and_apostrophe_normalization():
    assert tokenize("меҳнат таътилининг давомийлиги", 'uz-Cyrl') == tokenize("mehnat taʼtilining davomiyligi")
    assert tokenize("ta'til") == tokenize('taʼtil') == tokenize('ta’til')

def test_wrong_script_is_rejected():
    with pytest.raises(ValueError, match='heading'):
        parse_document(HTML, {'id': 1, 'language': 'uz-Cyrl'}, '2026-11-06', 'https://www.lex.uz/docs/1')

def test_saved_source_hash_matches_bytes(tmp_path, monkeypatch):
    import hashlib
    import json
    import app.ingest as module
    html = HTML.replace('\n', '\r\n')
    monkeypatch.setattr(module, 'download', lambda client, url: html)
    monkeypatch.setattr(module.time, 'sleep', lambda seconds: None)
    manifest = tmp_path/'sources.json'
    manifest.write_text(json.dumps([{'id': -1, 'language': 'uz-Latn'}]))
    report = module.ingest(manifest, tmp_path/'corpus.jsonl', tmp_path/'raw', '2026-11-06')
    doc = report['documents'][0]
    assert hashlib.sha256((tmp_path/'raw'/doc['raw_file']).read_bytes()).hexdigest() == doc['source_sha256']
