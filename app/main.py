import asyncio
import hmac
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles

from app.engine import Engine
from app.models import Batch
from app.store import Conflict, Store
from app.coverage import describe_corpus

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def create_app(db_path=None, corpus_path=None, api_key=None, rate_interval=1.0, sync_timeout=110):
    key = api_key or os.environ.get('RAG_API_KEY')
    if not key or len(key) < 16:
        raise RuntimeError('Set RAG_API_KEY to a secret of at least 16 characters')
    store = Store(db_path or os.environ.get('RAG_DB', str(PROJECT_ROOT / 'data/rag.sqlite3')))
    engine = Engine(corpus_path or os.environ.get('RAG_CORPUS', str(PROJECT_ROOT / 'data/lex.jsonl')))
    coverage = describe_corpus(engine.chunks)
    pool = ThreadPoolExecutor(max_workers=4)
    lock = threading.Lock()
    last = [0.0]

    @asynccontextmanager
    async def lifespan(app):
        store.recover()
        yield
        pool.shutdown(wait=True)

    app = FastAPI(title='Lex RAG API', version='0.4.0', lifespan=lifespan)
    bearer = HTTPBearer(auto_error=False)

    def auth(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if credentials is None or not hmac.compare_digest(credentials.credentials.encode(), key.encode()):
            raise HTTPException(401, 'Invalid API key', headers={'WWW-Authenticate': 'Bearer'})

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse(status_code=400, content={'error': {'code': 'VALIDATION_ERROR', 'message': 'Invalid request', 'details': [{'location': list(e['loc']), 'message': e['msg']} for e in exc.errors()]}})

    @app.get('/v1/health')
    def health():
        return {'status': 'ok', 'index_ready': bool(engine.chunks)}

    @app.get('/v1/meta', dependencies=[Depends(auth)])
    def meta():
        return engine.system

    @app.get('/v1/coverage', dependencies=[Depends(auth)])
    def corpus_coverage():
        return coverage

    # The interface uses the existing authenticated batch API on the same origin.
    web_dir = Path(__file__).resolve().parent / 'web'
    app.mount('/assets', StaticFiles(directory=web_dir), name='assets')

    @app.get('/', include_in_schema=False)
    def web_interface():
        return FileResponse(web_dir / 'index.html', headers={
            'Cache-Control': 'no-store',
            'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
            'Referrer-Policy': 'no-referrer',
            'X-Content-Type-Options': 'nosniff',
        })

    def process(batch):
        start = time.perf_counter()
        received = datetime.now(timezone.utc).isoformat()
        try:
            results = []
            for item in batch.items:
                try:
                    results.append(engine.answer(item, batch.options))
                except Exception:
                    results.append({'id': item.id, 'status': 'error', 'answer': None, 'no_answer': False, 'answer_language': item.language or 'uz-Latn', 'citations': [], 'contexts': [], 'timing': {'retrieval_ms': 0, 'rerank_ms': 0, 'generation_ms': 0, 'total_ms': 0}, 'error': {'code': 'RETRIEVAL_FAILED', 'message': 'Question processing failed', 'retryable': True}})
            result = {'run_id': batch.run_id, 'batch_id': batch.batch_id, 'status': 'completed', 'system': engine.system,
                      'timing': {'received_at': received, 'completed_at': datetime.now(timezone.utc).isoformat(), 'total_ms': round((time.perf_counter() - start) * 1000, 3)},
                      'summary': {'total': len(results), **{s: sum(r['status'] == s for r in results) for s in ('ok', 'no_answer', 'error')}}, 'results': results}
        except Exception:
            result = {'run_id': batch.run_id, 'batch_id': batch.batch_id, 'status': 'failed', 'system': engine.system, 'error': {'code': 'BATCH_FAILED', 'message': 'Batch processing failed', 'retryable': False}}
        result['seed'] = batch.options.seed
        store.save(batch.batch_id, result)
        return result

    @app.post('/v1/rag/batch', dependencies=[Depends(auth)])
    async def submit(batch: Batch):
        with lock:
            cached = store.get(batch.batch_id)
            if cached is None:
                now = time.monotonic()
                if now - last[0] < rate_interval:
                    raise HTTPException(429, 'Rate limit exceeded', headers={'Retry-After': '1'})
                last[0] = now
            try:
                fresh, stored = store.reserve(batch)
            except Conflict:
                raise HTTPException(409, 'batch_id already has different content')
            if not fresh:
                return JSONResponse(stored, status_code=202 if stored['status'] == 'processing' else 200)
            future = pool.submit(process, batch)
        try:
            result = await asyncio.wait_for(asyncio.shield(asyncio.wrap_future(future)), timeout=sync_timeout)
            return result
        except asyncio.TimeoutError:
            return JSONResponse(stored, status_code=202)

    @app.get('/v1/rag/batch/{batch_id}', dependencies=[Depends(auth)])
    def get_batch(batch_id: str):
        result = store.get(batch_id)
        if result is None:
            raise HTTPException(404, 'Batch not found')
        return JSONResponse(result, status_code=202 if result['status'] == 'processing' else 200)

    return app
