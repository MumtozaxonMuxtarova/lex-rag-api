"""Start the local server and open the interface after health becomes ready."""
import argparse
import http.client
import threading
import time
import webbrowser
import uvicorn

def open_when_ready(port):
    for _ in range(60):
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=1)
        try:
            connection.request('GET', '/v1/health')
            response = connection.getresponse()
            response.read()
            if response.status == 200:
                webbrowser.open(f'http://127.0.0.1:{port}')
                return
        except OSError:
            pass
        finally:
            connection.close()
        time.sleep(.5)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('Port must be between 1024 and 65535')
    if not args.no_browser:
        threading.Thread(target=open_when_ready, args=(args.port,), daemon=True).start()
    uvicorn.run('app.main:create_app', factory=True, host='127.0.0.1', port=args.port)
