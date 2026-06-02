import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import execute, query


def _find_municipality(name):
    if not name:
        return None
    municipality = query(
        "SELECT id, nome FROM municipios WHERE nome ILIKE %s LIMIT 1",
        (name,),
        one=True,
    )
    if not municipality:
        raise SystemExit(f"Município não encontrado: {name}")
    return municipality


def _find_action(action_id):
    if not action_id:
        return None
    action = query(
        "SELECT id, municipio_id FROM triagem_acoes WHERE id = %s",
        (action_id,),
        one=True,
    )
    if not action:
        raise SystemExit(f"Ação de triagem não encontrada: {action_id}")
    return action


def _existing_location(args, municipality_id):
    if args.scope == 'municipio':
        return query(
            "SELECT id FROM territorial_locations WHERE scope = 'municipio' AND municipio_id = %s LIMIT 1",
            (municipality_id,),
            one=True,
        )
    if args.scope == 'bairro':
        return query(
            """
            SELECT id
            FROM territorial_locations
            WHERE scope = 'bairro'
              AND LOWER(neighborhood) = LOWER(%s)
              AND COALESCE(municipio_id, 0) = COALESCE(%s, 0)
            LIMIT 1
            """,
            (args.bairro, municipality_id),
            one=True,
        )
    if args.scope == 'unidade':
        return query(
            """
            SELECT id
            FROM territorial_locations
            WHERE scope = 'unidade'
              AND LOWER(unit_name) = LOWER(%s)
              AND COALESCE(municipio_id, 0) = COALESCE(%s, 0)
            LIMIT 1
            """,
            (args.unidade, municipality_id),
            one=True,
        )
    if args.scope == 'triagem_acao':
        return query(
            "SELECT id FROM territorial_locations WHERE scope = 'triagem_acao' AND triagem_acao_id = %s LIMIT 1",
            (args.triagem_acao_id,),
            one=True,
        )
    raise SystemExit(f"Escopo inválido: {args.scope}")


def upsert_location(args):
    municipality = _find_municipality(args.municipio)
    action = _find_action(args.triagem_acao_id)
    municipality_id = municipality['id'] if municipality else None
    if action and not municipality_id:
        municipality_id = action['municipio_id']

    if args.scope == 'municipio' and not municipality_id:
        raise SystemExit("--municipio é obrigatório para scope=municipio")
    if args.scope == 'bairro' and not args.bairro:
        raise SystemExit("--bairro é obrigatório para scope=bairro")
    if args.scope == 'unidade' and not args.unidade:
        raise SystemExit("--unidade é obrigatório para scope=unidade")
    if args.scope == 'triagem_acao' and not args.triagem_acao_id:
        raise SystemExit("--triagem-acao-id é obrigatório para scope=triagem_acao")

    existing = _existing_location(args, municipality_id)
    params = (
        args.scope,
        municipality_id,
        args.bairro,
        args.unidade,
        args.triagem_acao_id,
        args.latitude,
        args.longitude,
        args.source,
        args.accuracy,
        args.notes,
    )

    if existing:
        location_id = execute(
            """
            UPDATE territorial_locations
            SET scope = %s,
                municipio_id = %s,
                neighborhood = %s,
                unit_name = %s,
                triagem_acao_id = %s,
                latitude = %s,
                longitude = %s,
                source = %s,
                accuracy = %s,
                notes = %s,
                active = TRUE,
                updated_at = NOW()
            WHERE id = %s
            RETURNING id
            """,
            (*params, existing['id']),
        )
    else:
        location_id = execute(
            """
            INSERT INTO territorial_locations (
                scope, municipio_id, neighborhood, unit_name, triagem_acao_id,
                latitude, longitude, source, accuracy, notes
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            params,
        )

    print(f"Coordenada territorial salva: id={location_id}")


def parse_args():
    parser = argparse.ArgumentParser(description='Cadastra ou atualiza coordenadas territoriais do mapa epidemiológico.')
    parser.add_argument('--scope', required=True, choices=['municipio', 'bairro', 'unidade', 'triagem_acao'])
    parser.add_argument('--municipio')
    parser.add_argument('--bairro')
    parser.add_argument('--unidade')
    parser.add_argument('--triagem-acao-id', dest='triagem_acao_id', type=int)
    parser.add_argument('--lat', dest='latitude', required=True, type=float)
    parser.add_argument('--lon', dest='longitude', required=True, type=float)
    parser.add_argument('--source', default='manual')
    parser.add_argument('--accuracy', default='informada manualmente')
    parser.add_argument('--notes', default='')
    return parser.parse_args()


if __name__ == '__main__':
    upsert_location(parse_args())
