"""Real-corpus BM25 retrieval and source-only extractive answers."""
import hashlib
import json
import re
import time
from datetime import date
from pathlib import Path
from app.retrieval import BM25Index, best_passage, normalize, query_subjects, rewrite_query

def tokens(text):
    text = text.casefold()
    for mark in ['ʻ', 'ʼ', '‘', '’', '`']:
        text = text.replace(mark, "'")
    return set(re.findall(r"[^\W_]+(?:'[^\W_]+)?", text))

def detect_language(text):
    if re.search('[а-яА-ЯёЁўқғҳЎҚҒҲ]', text):
        return 'uz-Cyrl' if re.search('[ўқғҳЎҚҒҲ]', text) or any(t in normalize(text) for t in ('mehnat', 'tatil', 'qancha', 'qanday', 'muddat', 'yillik', 'bitim', 'tushuncha', 'shartnoma', 'xodim', 'fuqaro', 'layoqat', 'huquq', 'majburiyat', 'dastlabki', 'sinov', 'umumiy')) else 'ru'
    return 'uz-Latn'

class Engine:
    def __init__(self, corpus):
        path = Path(corpus)
        raw = path.read_bytes() if path.exists() else b''
        self.chunks = [json.loads(line) for line in raw.decode('utf-8-sig').splitlines() if line.strip()]
        required = {'chunk_id', 'doc_id', 'doc_title', 'doc_type', 'url', 'article', 'part', 'edition_date', 'valid_from', 'valid_to', 'doc_status', 'text', 'language', 'snapshot_date'}
        ids = set()
        for chunk in self.chunks:
            if not required <= chunk.keys():
                raise ValueError(f'Missing corpus fields: {required - chunk.keys()}')
            if not re.fullmatch(r'lex:\d+', chunk['doc_id']):
                raise ValueError('doc_id must contain a lex.uz document number')
            number = chunk['doc_id'].split(':')[1]
            if chunk['url'] not in (f'https://lex.uz/docs/{number}', f'https://lex.uz/docs/-{number}'):
                raise ValueError('URL and doc_id must agree')
            if chunk['chunk_id'] in ids or not chunk['text'].strip():
                raise ValueError('Duplicate chunk ID or empty text')
            ids.add(chunk['chunk_id'])
            for field in ('edition_date', 'valid_from', 'snapshot_date'):
                date.fromisoformat(chunk[field])
            if chunk['valid_to']:
                if date.fromisoformat(chunk['valid_to']) <= date.fromisoformat(chunk['valid_from']):
                    raise ValueError('Invalid validity interval')
            if chunk['language'] not in ('uz-Latn', 'uz-Cyrl', 'ru'):
                raise ValueError('Invalid corpus language')
        self.index = BM25Index(self.chunks)
        translations_path = Path(__file__).resolve().parent.parent / 'sources' / 'lex.json'
        translation_raw = translations_path.read_bytes() if translations_path.exists() else b'[]'
        self.translation_groups = {f"lex:{abs(s['id'])}": s.get('translation_group', f"lex:{abs(s['id'])}") for s in json.loads(translation_raw)}
        self.translations = {}
        for c in self.chunks:
            group = c.get('translation_group') or self.translation_groups.get(c['doc_id'], c['doc_id'])
            self.translations.setdefault((group, c['language'], c.get('article_number', c['article'])), []).append(c)
        self.system = {
            'pipeline_version': '0.4.0', 'llm_model': None,
            'embedding_model': None, 'reranker': 'lexical-title-v2',
            'query_rewriter': 'uz-colloquial-rules-v1',
            'implementation_version': hashlib.sha256(b''.join((Path(__file__).parent / name).read_bytes() for name in ('engine.py', 'retrieval.py', 'models.py', 'main.py', 'store.py', 'coverage.py'))).hexdigest()[:16],
            'index_version': hashlib.sha256(raw).hexdigest()[:16],
            'lex_snapshot_date': min((c['snapshot_date'] for c in self.chunks), default=None),
            'mode': 'bm25-multisource-extractive',
            'documents': len({(c['doc_id'], c['language']) for c in self.chunks}),
            'chunks': len(self.chunks),
            'translation_map_version': hashlib.sha256(translation_raw).hexdigest()[:16],
        }

    def answer(self, item, options):
        start = time.perf_counter()
        language = item.language or detect_language(item.question)
        output_language = language if options.answer_language == 'auto' else options.answer_language
        result = {'id': item.id, 'status': 'no_answer', 'answer': None,
                  'answer_language': output_language, 'no_answer': True,
                  'citations': [], 'contexts': [], 'error': None}
        if not self.chunks:
            result.update(status='error', no_answer=False, error={
                'code': 'INDEX_UNAVAILABLE', 'message': 'Import a verified lex.uz corpus first', 'retryable': False})
        elif not all(self.date_available(lang, options.as_of_date.isoformat()) for lang in {language, output_language}):
            result.update(status='error', no_answer=False, error={
                'code': 'SNAPSHOT_DATE_UNAVAILABLE',
                'message': 'Requested date is outside the fully imported edition window; import that date first',
                'retryable': False})
        else:
            day = options.as_of_date.isoformat()
            retrieval_start = time.perf_counter()
            ranked = self.index.search(item.question, language, day)
            if language != output_language:
                projected = []
                for score, rerank, c in ranked:
                    group = c.get('translation_group') or self.translation_groups.get(c['doc_id'], c['doc_id'])
                    equivalents = self.translations.get((group, output_language, c.get('article_number', c['article'])), [])
                    translated = next((t for t in equivalents if t['valid_from'] <= day <= t['snapshot_date'] and (not t['valid_to'] or day < t['valid_to']) and t['doc_status'] == 'amalda'), None)
                    if translated:
                        projected.append((score, rerank, translated))
                if ranked and not projected:
                    result.update(status='error', no_answer=False, error={'code': 'TRANSLATION_UNAVAILABLE', 'message': 'No verified equivalent article exists in the requested answer language', 'retryable': False})
                ranked = projected
            retrieval_ms = (time.perf_counter() - retrieval_start) * 1000
            selected = ranked[:options.top_k]
            generation_start = time.perf_counter()
            subjects = query_subjects(item.question)
            count = min(len(subjects), len(selected))
            contexts = [dict(rank=i, chunk_id=c['chunk_id'], doc_id=c['doc_id'], article=c['article'], text=c['text'], retrieval_score=score, rerank_score=rerank, used_in_answer=i <= count) for i, (score, rerank, c) in enumerate(selected, 1)]
            if selected:
                citations, passages = [], []
                for ref, (_, _, c) in enumerate(selected[:count], 1):
                    citation = {key: c[key] for key in ('doc_id', 'doc_title', 'doc_type', 'url', 'article', 'part', 'edition_date', 'doc_status', 'chunk_id')}
                    passage = best_passage(c, item.question)
                    citation.update(ref=ref, quote=passage, valid_from=c['valid_from'], valid_to=c['valid_to'])
                    for key in ('source_url', 'source_anchor', 'edition_label'):
                        if key in c:
                            citation[key] = c[key]
                    citations.append(citation)
                    passages.append(passage + f' [{ref}]')
                result.update(status='ok', no_answer=False, answer='\n\n'.join(passages), citations=citations)
            # Keep cited contexts even when full context output is disabled.
            result['contexts'] = contexts if options.return_contexts else [c for c in contexts if c['used_in_answer']]
            if options.return_debug:
                result['debug'] = {'rewritten_query': rewrite_query(item.question, language), 'retrieval_language': language, 'retrieved_total': len(ranked), 'mode': self.system['mode'], 'subjects': subjects}
            generation_ms = (time.perf_counter() - generation_start) * 1000
        elapsed = round((time.perf_counter() - start) * 1000, 3)
        result['timing'] = {'retrieval_ms': round(locals().get('retrieval_ms', 0), 3), 'rerank_ms': 0, 'generation_ms': round(locals().get('generation_ms', 0), 3), 'total_ms': elapsed}
        return result

    def date_available(self, language, day):
        groups = {}
        for c in self.chunks:
            if c['language'] == language and 'source_sha256' in c:
                groups.setdefault(c['doc_id'], set()).add((c['valid_from'], c['valid_to'], c['snapshot_date']))
        # Each document needs at least one verified edition covering the date.
        # Other editions of that same document must not invalidate the request.
        return all(any(start <= day <= snapshot and (end is None or day < end)
                       for start, end, snapshot in windows) for windows in groups.values())
