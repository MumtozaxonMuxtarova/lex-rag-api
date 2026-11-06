"""Compare preserved runs without mixing different test suites."""
import argparse
import json
from pathlib import Path


def compare(before, after, output):
    folders = [Path('evaluation') / name for name in (before, after)]
    reports = [json.loads((folder / 'report.json').read_text(encoding='utf-8')) for folder in folders]
    if reports[0]['dataset_sha256'] != reports[1]['dataset_sha256']:
        raise ValueError('Dataset hashes differ: these runs are not directly comparable')
    systems = [json.loads((folder / 'b01.json').read_text(encoding='utf-8'))['system'] for folder in folders]
    common = reports[0]['metrics'].keys() & reports[1]['metrics'].keys()
    metrics = {key: {'before': reports[0]['metrics'][key], 'after': reports[1]['metrics'][key],
                     'delta': reports[1]['metrics'][key] - reports[0]['metrics'][key]}
               for key in sorted(common) if all(isinstance(r['metrics'][key], (int, float)) for r in reports)}
    comparison = {'before': before, 'after': after, 'dataset_sha256': reports[0]['dataset_sha256'],
                  'systems': {'before': systems[0], 'after': systems[1]}, 'metrics': metrics,
                  'note': 'Same frozen development suite; quality proxies are not independent semantic judgments. Timing depends on transport and machine load.'}
    Path(output).write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Compared {before} and {after}; dataset hash matches.')
    return comparison


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('before')
    parser.add_argument('after')
    parser.add_argument('--output', default='evaluation/tz-comparison.json')
    args = parser.parse_args()
    compare(args.before, args.after, args.output)
