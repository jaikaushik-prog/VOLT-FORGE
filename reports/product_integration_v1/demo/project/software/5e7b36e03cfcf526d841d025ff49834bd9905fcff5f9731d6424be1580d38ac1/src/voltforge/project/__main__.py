"""JSON-in/JSON-out CLI adapter for the documented synchronous Python contract."""
import argparse
import json
from pathlib import Path
import sys
from .service import dispatch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--request', type=Path, help='JSON request file; omit to read stdin')
    args = parser.parse_args()
    try:
        request = json.loads(args.request.read_text(encoding='utf-8') if args.request else sys.stdin.read())
        response = dispatch(args.project, request)
    except (ValueError, OSError) as exc:
        response = {'status': 'error', 'error': {'code': 'invalid_request', 'message': str(exc)}}
    print(json.dumps(response, indent=2, allow_nan=False))
    return 0 if response['status'] == 'ok' else 2


if __name__ == '__main__':
    raise SystemExit(main())
