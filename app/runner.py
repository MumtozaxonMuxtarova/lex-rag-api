"""Sequential batch client with bounded retries, async polling and raw JSON output."""
import json
import time
from pathlib import Path


def submit_and_wait(client, payload, *, deadline_seconds=1800, sleep=time.sleep):
    deadline = time.monotonic() + deadline_seconds
    response = None
    skip_backoff = False
    for attempt, delay in enumerate((0, 5, 15, 45)):
        if delay and not skip_backoff:
            sleep(delay)
        skip_backoff = False
        try:
            response = client.post('/v1/rag/batch', json=payload)
        except Exception as exc:
            # Only transport failures can be retried; invalid data must surface.
            import httpx
            if not isinstance(exc, httpx.TransportError) or attempt == 3:
                raise
            continue
        if response.status_code == 429:
            sleep(max(1, min(120, float(response.headers.get('Retry-After', '1')))))
            skip_backoff = True
        elif response.status_code not in (500, 503, 504):
            break
    if response is None:
        raise RuntimeError('No batch response')
    response.raise_for_status()
    while response.status_code in (202, 429, 500, 503, 504):
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Batch {payload['batch_id']} remains processing; resume with the same ID")
        sleep(1)
        try:
            response = client.get('/v1/rag/batch/' + payload['batch_id'])
        except Exception as exc:
            import httpx
            if not isinstance(exc, httpx.TransportError):
                raise
            sleep(5)
            continue
        if response.status_code in (429, 500, 503, 504):
            sleep(5)
            continue
        response.raise_for_status()
    body = response.json()
    if body.get('status') != 'completed':
        raise RuntimeError(f"Batch failed: {body.get('error')}")
    actual = [r['id'] for r in body['results']]
    if len(actual) != len(set(actual)) or set(actual) != {q['id'] for q in payload['items']}:
        raise ValueError('Batch result IDs do not match the request')
    return body


def run_batches(client, questions, options, run_id, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    total = (len(questions) + 9) // 10
    for start in range(0, len(questions), 10):
        group = questions[start:start + 10]
        number = start // 10 + 1
        dates = {q.get('as_of_date', options['as_of_date']) for q in group}
        if len(dates) != 1:
            raise ValueError('All questions in a batch must share as_of_date')
        payload = {
            'run_id': run_id, 'batch_id': f'{run_id}-b{number:02}',
            'batch_index': number, 'total_batches': total,
            'options': {**options, 'as_of_date': dates.pop()},
            'items': [{k: q[k] for k in ('id', 'question', 'language') if k in q} for q in group],
        }
        body = submit_and_wait(client, payload)
        (output / f'b{number:02}.json').write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding='utf-8')

