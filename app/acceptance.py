"""Exercise the real HTTP server and preserve a complete 100-question run."""
import argparse
import json
import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

from app.evaluate import evaluate


def run(label, review_path=None):
    if not label or Path(label).name != label or label in ('.', '..'):
        raise ValueError('Label must be a single directory name')
    root = Path(__file__).resolve().parent.parent
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    key = secrets.token_urlsafe(32)
    env = dict(os.environ, RAG_API_KEY=key, RAG_DB=str(root / '.runtime' / f'{label}.sqlite3'))
    log_path = root / 'reports' / f'{label}-server.log'
    previous_key = os.environ.get('RAG_API_KEY')
    os.environ['RAG_API_KEY'] = key
    base = f'http://127.0.0.1:{port}'
    try:
        with log_path.open('w', encoding='utf-8') as log:
            server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:create_app', '--factory', '--host', '127.0.0.1', '--port', str(port)],
                                      cwd=root, env=env, stdout=log, stderr=log,
                                      creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            try:
                deadline = time.monotonic() + 180
                while True:
                    if server.poll() is not None:
                        raise RuntimeError(f'Server exited; inspect {log_path}')
                    try:
                        ready = httpx.get(base + '/v1/health', timeout=1)
                        if ready.status_code == 200:
                            assert ready.json()['index_ready']
                            break
                    except httpx.TransportError:
                        pass
                    if time.monotonic() > deadline:
                        raise TimeoutError('Server did not become ready')
                    time.sleep(.5)
                with httpx.Client(base_url=base, timeout=125) as client:
                    assert client.get('/').status_code == 200
                    assert client.get('/assets/app.js').status_code == 200
                    assert client.get('/v1/meta').status_code == 401
                    client.headers['Authorization'] = f'Bearer {key}'
                    meta = client.get('/v1/meta').json()
                    coverage = client.get('/v1/coverage').json()
                report = evaluate(label, base_url=base, review_path=review_path)
                checks = {'verified': True, 'transport': 'real loopback HTTP',
                          'health': True, 'frontend': True, 'unauthorized_rejected': True,
                          'system': meta, 'coverage': coverage, 'metrics': report['metrics'],
                          'dataset_sha256': report['dataset_sha256']}
                (root / 'reports' / 'acceptance.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding='utf-8')
            finally:
                server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=10)
    finally:
        if previous_key is None:
            os.environ.pop('RAG_API_KEY', None)
        else:
            os.environ['RAG_API_KEY'] = previous_key


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', required=True)
    parser.add_argument('--review', help='Completed review for the same dataset/system/answers')
    args = parser.parse_args()
    run(args.label, args.review)
