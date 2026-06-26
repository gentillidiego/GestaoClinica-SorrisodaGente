from services.dental_cid_service import (
    DENTAL_CIDS,
    get_dental_cid,
    get_dental_cid_groups,
    is_valid_dental_cid,
)


def test_dental_cid_catalog_is_unique_and_covers_official_oral_groups():
    codes = [item.code for item in DENTAL_CIDS]

    assert len(codes) == len(set(codes))
    assert len(codes) == 113
    for prefix in (f'K{number:02d}' for number in range(15)):
        assert any(code.startswith(prefix) for code in codes)


def test_dental_cid_lookup_returns_short_clinical_description():
    pulpitis = get_dental_cid('k04.0')

    assert pulpitis.code == 'K04.0'
    assert pulpitis.description == 'Pulpite'
    assert pulpitis.group == 'Polpa e tecidos periapicais'
    assert pulpitis.label == 'K04.0 — Pulpite'
    assert is_valid_dental_cid('K04.0')
    assert not is_valid_dental_cid('A00.0')


def test_dental_cids_are_grouped_for_the_atestado_selector():
    groups = get_dental_cid_groups()

    assert groups[0]['label'] == 'Desenvolvimento e erupção dentária'
    assert groups[-1]['label'] == 'Traumas e atendimento odontológico'
    assert sum(len(group['items']) for group in groups) == len(DENTAL_CIDS)
