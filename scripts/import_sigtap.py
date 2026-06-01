#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import app
from services.sigtap_service import (
    import_sigtap_zip,
    import_tb_procedimento_file,
    seed_odontology_sigtap,
)


def main():
    parser = argparse.ArgumentParser(description='Importa procedimentos SIGTAP/DataSUS.')
    parser.add_argument('--competence', required=True, help='Competência SIGTAP no formato AAAAMM.')
    parser.add_argument('--zip', dest='zip_path', help='Caminho do ZIP oficial SIGTAP.')
    parser.add_argument('--tb-procedimento', help='Caminho do arquivo TB_PROCEDIMENTO.TXT extraído.')
    parser.add_argument(
        '--all-procedures',
        action='store_true',
        help='Importa todos os procedimentos; padrão importa apenas recorte odontológico.'
    )
    parser.add_argument(
        '--seed-only',
        action='store_true',
        help='Carrega apenas a pré-carga odontológica local.'
    )
    args = parser.parse_args()

    with app.app_context():
        if args.seed_only:
            imported = seed_odontology_sigtap(args.competence)
        elif args.zip_path:
            imported = import_sigtap_zip(
                args.zip_path,
                args.competence,
                odontologia_only=not args.all_procedures,
            )
        elif args.tb_procedimento:
            imported = import_tb_procedimento_file(
                args.tb_procedimento,
                args.competence,
                odontologia_only=not args.all_procedures,
            )
        else:
            parser.error('Informe --zip, --tb-procedimento ou --seed-only.')

    print(f'Procedimentos SIGTAP importados: {imported}')


if __name__ == '__main__':
    main()
