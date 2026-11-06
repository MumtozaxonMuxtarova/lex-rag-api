"""Evaluate a frozen source-grounded dataset through ten sequential API batches."""
import argparse
import hashlib
import json
import tempfile
import os
import math
import httpx
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import create_app
from app.runner import run_batches


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)] if ordered else None

def evaluate(label, dataset='evaluation/questions.json', base_url=None, review_path=None):
    if not label or Path(label).name != label or label in ('.', '..'):
        raise ValueError('Label must be a single directory name')
    path = Path(dataset)
    raw = path.read_bytes()
    questions = json.loads(raw)['questions']
    assert len(questions) == 100 and len({q['id'] for q in questions}) == 100
    corpus = Path('data/lex.jsonl')
    chunks = {c['chunk_id']: c for c in map(json.loads, corpus.read_text(encoding='utf-8').splitlines())}
    assert hashlib.sha256(corpus.read_bytes()).hexdigest() == json.loads(raw)['corpus_sha256']
    for q in questions:
        for source in q['expected_sources']:
            chunk = chunks[source['chunk_id']]
            assert source['quote'] in chunk['text']
            assert source['doc_id'] == chunk['doc_id'] and source['article'] == chunk['article']
    output = Path('evaluation') / label
    if output.exists() and list(output.glob('b[0-9][0-9].json')):
        raise ValueError('Run already exists; choose a new label to preserve comparison evidence')
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        if base_url and not os.environ.get('RAG_API_KEY'):
            raise ValueError('Set RAG_API_KEY for a remote API run')
        session = httpx.Client(base_url=base_url.rstrip('/'), timeout=125) if base_url else TestClient(create_app(Path(tmp)/'db.sqlite3', corpus, api_key='evaluation-local-key-only', rate_interval=0))
        with session as client:
            client.headers['Authorization'] = 'Bearer ' + (os.environ['RAG_API_KEY'] if base_url else 'evaluation-local-key-only')
            run_batches(client, questions, {'as_of_date': json.loads(raw).get('as_of_date', '2026-11-06'), 'top_k': 5, 'temperature': 0, 'seed': 42}, label, output)
    return score_saved(label, dataset, review_path, base_url)


def score_saved(label, dataset, review_path=None, base_url=None):
    output = Path('evaluation') / label
    raw = Path(dataset).read_bytes()
    frozen = json.loads(raw)
    questions = frozen['questions']
    results, versions = {}, []
    for i in range(1, 11):
        body = json.loads((output / f'b{i:02}.json').read_bytes())
        expected = {q['id'] for q in questions[(i-1)*10:i*10]}
        rows = body['results']
        if (body.get('seed') != 42 or body['run_id'] != label or
                body['batch_id'] != f'{label}-b{i:02}' or body['status'] != 'completed' or
                len(rows) != 10 or {r['id'] for r in rows} != expected):
            raise ValueError(f'Invalid saved batch b{i:02}')
        versions.append(body['system'])
        results.update({r['id']: r for r in rows})
    if any(v != versions[0] for v in versions) or versions[0]['index_version'] != frozen['corpus_sha256'][:16]:
        raise ValueError('Inconsistent saved index version')
    detail = []
    for q in questions:
        r = results[q['id']]
        targets = {(s['doc_id'], s['article']) for s in q['expected_sources']}
        found = [(c['doc_id'], c['article']) for c in r['contexts'][:5]]
        ranks = [i for i, candidate in enumerate(found, 1) if candidate in targets]
        rank = min(ranks, default=None)
        citation_contexts = {c['chunk_id']: c for c in r['contexts']}
        citations = r['citations']
        exact_matches = sum(s['quote'] in (r['answer'] or '') for s in q['expected_sources'])
        detail.append({'id': q['id'], 'category': q['category'], 'question': q['question'], 'answerable': q['answerable'],
                       'status': r['status'], 'first_relevant_rank': rank,
                       'hit1': rank == 1, 'hit5': rank is not None,
                       'reciprocal_rank_at5': 1/rank if rank else 0,
                       'all_expected_in_top5': bool(targets) and targets <= set(found),
                       'document_hit5': any(doc == s[0] for doc, _ in found for s in targets),
                       'recall_at5': len(targets & set(found)) / len(targets) if targets else None,
                       'gold_precision_at5': sum(c in targets for c in found) / len(found) if found else 0,
                       'exact_answer_score': (2 if exact_matches == len(targets) else 1 if exact_matches else 0) if targets else (2 if r['no_answer'] else 0),
                       'citation_count': len(citations),
                       'verbatim_quotes': sum(c['chunk_id'] in citation_contexts and c['quote'] in citation_contexts[c['chunk_id']]['text'] for c in citations),
                       'gold_citations': sum((c['doc_id'], c['article']) in targets for c in citations),
                       'fabricated_sources': sum(c['chunk_id'] not in citation_contexts or c['quote'] not in citation_contexts[c['chunk_id']]['text'] or c['doc_id'] != citation_contexts[c['chunk_id']]['doc_id'] or c['article'] != citation_contexts[c['chunk_id']]['article'] or c['url'] not in {f"https://lex.uz/docs/{sign}{c['doc_id'].removeprefix('lex:')}" for sign in ('', '-')} for c in citations),
                       'out_of_date_citations': sum(not (c['valid_from'] <= q['as_of_date'] < (c['valid_to'] or '9999-12-31')) or c['doc_status'] != 'amalda' for c in citations),
                       'total_ms': r['timing']['total_ms'],
                       'expected_sources': sorted(targets), 'returned_sources': found})
    answerable = [d for d in detail if d['answerable']]
    noanswer = [d for d in detail if not d['answerable']]
    metrics = {'total': 100, 'answerable': len(answerable), 'unanswerable': len(noanswer),
               'Hit@1': sum(d['hit1'] for d in answerable)/len(answerable),
               'Hit@5': sum(d['hit5'] for d in answerable)/len(answerable),
               'MRR@5': sum(d['reciprocal_rank_at5'] for d in answerable)/len(answerable),
               'no_result_answerable': sum(d['status'] == 'no_answer' for d in answerable),
               'expected_missing_top5': sum(not d['hit5'] for d in answerable),
               'wrong_top1_answerable': sum(d['status']=='ok' and not d['hit1'] for d in answerable),
               'no_answer_all': sum(d['status']=='no_answer' for d in detail),
               'correct_rejections': sum(d['status']=='no_answer' for d in noanswer),
               'false_answers_out_of_scope': sum(d['status']=='ok' for d in noanswer),
               'errors': sum(d['status'] in ('error','timeout') for d in detail),
               'multi_all_targets_top5': sum(d['all_expected_in_top5'] for d in detail if d['category']=='kop_manba')}
    mean = lambda key: sum(d[key] for d in answerable) / len(answerable)
    citation_total = sum(d['citation_count'] for d in detail)
    metrics.update({
        'Hit@5_document': mean('document_hit5'), 'Recall@5': mean('recall_at5'),
        'gold_context_precision_at5': mean('gold_precision_at5'),
        'exact_answer_correctness_proxy_0_2': sum(d['exact_answer_score'] for d in detail) / len(detail),
        'verbatim_quote_rate': sum(d['verbatim_quotes'] for d in detail) / citation_total if citation_total else None,
        'gold_citation_accuracy_proxy': sum(d['gold_citations'] for d in detail) / citation_total if citation_total else None,
        'fabricated_sources': sum(d['fabricated_sources'] for d in detail),
        'out_of_date_citations': sum(d['out_of_date_citations'] for d in detail),
        'latency_p50_ms': percentile([d['total_ms'] for d in detail], .5),
        'latency_p95_ms': percentile([d['total_ms'] for d in detail], .95),
        'error_rate': metrics['errors'] / len(detail),
    })
    review_payload = json.loads(Path(review_path).read_text(encoding='utf-8')) if review_path else []
    if isinstance(review_payload, dict):
        if review_payload.get('dataset_sha256') != hashlib.sha256(raw).hexdigest() or review_payload.get('system') != versions[0]:
            raise ValueError('Review dataset/system does not match this run')
        reviews = review_payload['reviews']
    else:
        reviews = review_payload
    if reviews:
        by_id = {r['id']: r for r in reviews}
        if len(by_id) != 100 or set(by_id) != set(results):
            raise ValueError('Review must contain all 100 unique result IDs')
        for entry in reviews:
            if entry.get('answer_correctness') not in (0, 1, 2) or not isinstance(entry.get('faithful'), bool) or not isinstance(entry.get('citation_accurate'), bool):
                raise ValueError('Each review needs correctness 0/1/2 and boolean faithfulness/citation accuracy')
            ids = {c['chunk_id'] for c in results[entry['id']]['contexts']}
            if not set(entry['relevant_context_ids']) <= ids:
                raise ValueError('Reviewed relevant contexts must belong to the actual response')
            if 'answer' in entry and entry['answer'] != results[entry['id']]['answer']:
                raise ValueError('Review answer differs from the actual response')
        metrics.update({
            'answer_correctness': sum(r['answer_correctness'] for r in reviews) / 100,
            'faithfulness': sum(r['faithful'] for r in reviews if results[r['id']]['answer']) / max(1, sum(bool(r['answer']) for r in results.values())),
            'citation_accuracy': sum(r['citation_accurate'] for r in reviews if results[r['id']]['citations']) / max(1, sum(bool(r['citations']) for r in results.values())),
            'context_precision': sum(len(by_id[q['id']]['relevant_context_ids']) / max(1, len(results[q['id']]['contexts'])) for q in questions if q['answerable']) / len(answerable),
        })
    worksheet = [{'id': q['id'], 'question': q['question'], 'expected_answer': q.get('expected_answer') or '\n\n'.join(s['quote'] for s in q['expected_sources']),
                  'answer': results[q['id']]['answer'], 'contexts': results[q['id']]['contexts'],
                  'answer_correctness': None, 'faithful': None, 'citation_accurate': None,
                  'relevant_context_ids': [], 'reason': ''} for q in questions]
    (output/'review-template.json').write_text(json.dumps(worksheet, ensure_ascii=False, indent=2), encoding='utf-8')
    report = {'label': label, 'dataset_sha256': hashlib.sha256(raw).hexdigest(), 'metrics': metrics, 'semantic_review_complete': bool(reviews),
              'review': {'reviewer': review_payload.get('reviewer'), 'method': review_payload.get('method'), 'limitations': review_payload.get('limitations', []), 'sha256': hashlib.sha256(Path(review_path).read_bytes()).hexdigest()} if isinstance(review_payload, dict) else {'method': 'User supplied review'} if reviews else None,
              'limits': ['Source-derived development dataset, not an independent benchmark.', 'Exact-answer, quote and gold relevance measures are automatic proxies; semantic metrics require a completed review.', 'Retrieval and lexical reranking are measured together in retrieval_ms; rerank_ms=0 means no separate reranker.', 'Local in-process latency excludes network overhead.' if not base_url else 'Server timing excludes client network overhead.'],
              'method': 'Hit/MRR denominator=90 answerable questions; doc+article must both match. Multi-source hit accepts any listed relevant source; all-target coverage reported separately. MRR is truncated to the returned top5 (MRR@5).',
              'details': detail}
    (output/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return report

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', required=True)
    parser.add_argument('--dataset', default='evaluation/questions.json')
    parser.add_argument('--base-url', help='Test a running HTTP API instead of the in-process app')
    parser.add_argument('--review', help='Completed semantic review JSON; never sent to the API')
    args = parser.parse_args()
    evaluate(args.label, args.dataset, args.base_url, args.review)
