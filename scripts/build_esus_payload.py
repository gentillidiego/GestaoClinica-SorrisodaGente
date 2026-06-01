#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import app
from services.esus_export_service import build_esus_payload, register_esus_export_batch


def main():
    parser = argparse.ArgumentParser(description='Gera payload preliminar para integração e-SUS APS.')
    parser.add_argument('--month', help='Mês de referência no formato YYYY-MM.')
    parser.add_argument('--register', action='store_true', help='Registra lote draft no banco.')
    parser.add_argument('--output', help='Arquivo JSON de saída.')
    args = parser.parse_args()

    with app.app_context():
        if args.register:
            batch_id, payload = register_esus_export_batch(args.month)
            payload['batch_id'] = batch_id
        else:
            payload, payload_hash = build_esus_payload(args.month)
            payload['payload_hash'] = payload_hash

    content = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    if args.output:
        Path(args.output).write_text(content, encoding='utf-8')
        print(f'Payload e-SUS gerado: {args.output}')
    else:
        print(content)


if __name__ == '__main__':
    main()
