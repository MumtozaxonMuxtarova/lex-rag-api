import hashlib
import json
import sqlite3
from pathlib import Path
from contextlib import contextmanager

class Conflict(Exception):
    pass

class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS batches (id TEXT PRIMARY KEY, digest TEXT NOT NULL, response TEXT NOT NULL)')

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=30)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def reserve(self, request):
        # One transaction prevents concurrent retries from starting duplicate work.
        payload = request.model_dump(mode='json')
        # The date default must not change the identity of a retry on the next day.
        if 'as_of_date' not in request.options.model_fields_set:
            payload['options'].pop('as_of_date')
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT digest,response FROM batches WHERE id=?', (request.batch_id,)).fetchone()
            if row:
                if row[0] != digest:
                    raise Conflict()
                return False, json.loads(row[1])
            pending = {'run_id': request.run_id, 'batch_id': request.batch_id, 'status': 'processing', 'seed': request.options.seed}
            db.execute('INSERT INTO batches VALUES (?,?,?)', (request.batch_id, digest, json.dumps(pending)))
            return True, pending

    def save(self, batch_id, result):
        with self.connect() as db:
            db.execute('UPDATE batches SET response=? WHERE id=?', (json.dumps(result, ensure_ascii=False), batch_id))

    def get(self, batch_id):
        with self.connect() as db:
            row = db.execute('SELECT response FROM batches WHERE id=?', (batch_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def recover(self):
        # A process restart cannot silently leave an unfinished job polling forever.
        with self.connect() as db:
            for batch_id, raw in db.execute('SELECT id,response FROM batches').fetchall():
                result = json.loads(raw)
                if result['status'] == 'processing':
                    result.update(status='failed', error={'code': 'PROCESS_RESTARTED', 'message': 'Submit with a new batch_id', 'retryable': False})
                    db.execute('UPDATE batches SET response=? WHERE id=?', (json.dumps(result), batch_id))
