from dataclasses import dataclass


@dataclass(frozen=True)
class DentalCid:
    code: str
    description: str
    group: str

    @property
    def label(self):
        return f'{self.code} — {self.description}'


_GROUPS = (
    ('Desenvolvimento e erupção dentária', (
        ('K00.0', 'Anodontia, hipodontia ou oligodontia'),
        ('K00.1', 'Dentes supranumerários'),
        ('K00.2', 'Anomalias do tamanho e da forma dos dentes'),
        ('K00.3', 'Dentes manchados ou mosqueados'),
        ('K00.4', 'Distúrbios da formação dos dentes'),
        ('K00.5', 'Distúrbios hereditários da estrutura dentária'),
        ('K00.6', 'Distúrbios da erupção dentária'),
        ('K00.7', 'Síndrome da erupção dentária'),
        ('K00.8', 'Outros distúrbios do desenvolvimento dentário'),
        ('K00.9', 'Distúrbio do desenvolvimento dentário não especificado'),
        ('K01.0', 'Dentes inclusos'),
        ('K01.1', 'Dentes impactados'),
    )),
    ('Cárie dentária', (
        ('K02.0', 'Cárie limitada ao esmalte'),
        ('K02.1', 'Cárie da dentina'),
        ('K02.2', 'Cárie do cemento'),
        ('K02.3', 'Cárie dentária estabilizada'),
        ('K02.4', 'Odontoclasia'),
        ('K02.8', 'Outras cáries dentárias'),
        ('K02.9', 'Cárie dentária não especificada'),
    )),
    ('Outras doenças dos tecidos dentários', (
        ('K03.0', 'Atrição dentária excessiva'),
        ('K03.1', 'Abrasão dentária'),
        ('K03.2', 'Erosão dentária'),
        ('K03.3', 'Reabsorção patológica dos dentes'),
        ('K03.4', 'Hipercementose'),
        ('K03.5', 'Anquilose dentária'),
        ('K03.6', 'Depósitos nos dentes'),
        ('K03.7', 'Alterações pós-eruptivas da cor dos dentes'),
        ('K03.8', 'Outras doenças especificadas dos tecidos dentários'),
        ('K03.9', 'Doença dos tecidos dentários não especificada'),
    )),
    ('Polpa e tecidos periapicais', (
        ('K04.0', 'Pulpite'),
        ('K04.1', 'Necrose da polpa'),
        ('K04.2', 'Degeneração da polpa'),
        ('K04.3', 'Formação anormal de tecido duro na polpa'),
        ('K04.4', 'Periodontite apical aguda de origem pulpar'),
        ('K04.5', 'Periodontite apical crônica'),
        ('K04.6', 'Abscesso periapical com fístula'),
        ('K04.7', 'Abscesso periapical sem fístula'),
        ('K04.8', 'Cisto radicular'),
        ('K04.9', 'Outras doenças da polpa e tecidos periapicais'),
    )),
    ('Gengiva e periodonto', (
        ('K05.0', 'Gengivite aguda'),
        ('K05.1', 'Gengivite crônica'),
        ('K05.2', 'Periodontite aguda'),
        ('K05.3', 'Periodontite crônica'),
        ('K05.4', 'Periodontose'),
        ('K05.5', 'Outras doenças periodontais'),
        ('K05.6', 'Doença periodontal não especificada'),
        ('K06.0', 'Retração gengival'),
        ('K06.1', 'Hiperplasia gengival'),
        ('K06.2', 'Lesões gengivais associadas a trauma'),
        ('K06.8', 'Outros transtornos da gengiva e rebordo alveolar'),
        ('K06.9', 'Transtorno gengival não especificado'),
    )),
    ('Anomalias dentofaciais e articulação temporomandibular', (
        ('K07.0', 'Anomalias importantes do tamanho da mandíbula ou maxila'),
        ('K07.1', 'Anomalias da relação entre maxila e base do crânio'),
        ('K07.2', 'Anomalias da relação entre as arcadas dentárias'),
        ('K07.3', 'Anomalias da posição dos dentes'),
        ('K07.4', 'Má oclusão não especificada'),
        ('K07.5', 'Anormalidades dentofaciais funcionais'),
        ('K07.6', 'Transtornos da articulação temporomandibular'),
        ('K07.8', 'Outras anomalias dentofaciais'),
        ('K07.9', 'Anomalia dentofacial não especificada'),
    )),
    ('Perda dentária e estruturas de suporte', (
        ('K08.0', 'Esfoliação dentária por causas sistêmicas'),
        ('K08.1', 'Perda de dentes por acidente, extração ou doença periodontal'),
        ('K08.2', 'Atrofia do rebordo alveolar sem dentes'),
        ('K08.3', 'Raiz dentária retida'),
        ('K08.8', 'Outros transtornos dos dentes e estruturas de suporte'),
        ('K08.9', 'Transtorno dentário não especificado'),
    )),
    ('Cistos e doenças dos maxilares', (
        ('K09.0', 'Cistos odontogênicos de desenvolvimento'),
        ('K09.1', 'Cistos não odontogênicos de desenvolvimento'),
        ('K09.2', 'Outros cistos dos maxilares'),
        ('K09.8', 'Outros cistos da região oral'),
        ('K09.9', 'Cisto da região oral não especificado'),
        ('K10.0', 'Transtornos do desenvolvimento dos maxilares'),
        ('K10.1', 'Granuloma central de células gigantes'),
        ('K10.2', 'Afecções inflamatórias dos maxilares'),
        ('K10.3', 'Alveolite dos maxilares'),
        ('K10.8', 'Outras doenças especificadas dos maxilares'),
        ('K10.9', 'Doença dos maxilares não especificada'),
    )),
    ('Glândulas salivares', (
        ('K11.0', 'Atrofia de glândula salivar'),
        ('K11.1', 'Hipertrofia de glândula salivar'),
        ('K11.2', 'Sialadenite'),
        ('K11.3', 'Abscesso de glândula salivar'),
        ('K11.4', 'Fístula de glândula salivar'),
        ('K11.5', 'Sialolitíase'),
        ('K11.6', 'Mucocele de glândula salivar'),
        ('K11.7', 'Alterações da secreção salivar'),
        ('K11.8', 'Outras doenças das glândulas salivares'),
        ('K11.9', 'Doença de glândula salivar não especificada'),
    )),
    ('Estomatite, mucosa oral e lábios', (
        ('K12.0', 'Aftas orais recorrentes'),
        ('K12.1', 'Outras formas de estomatite'),
        ('K12.2', 'Celulite e abscesso da boca'),
        ('K12.3', 'Mucosite oral'),
        ('K12.8', 'Outras doenças da boca'),
        ('K12.9', 'Doença da boca não especificada'),
        ('K13.0', 'Doenças dos lábios'),
        ('K13.1', 'Mordedura da mucosa da bochecha ou dos lábios'),
        ('K13.2', 'Leucoplasia e outras alterações do epitélio oral'),
        ('K13.3', 'Leucoplasia pilosa'),
        ('K13.4', 'Granuloma e lesões semelhantes da mucosa oral'),
        ('K13.5', 'Fibrose submucosa oral'),
        ('K13.6', 'Hiperplasia irritativa da mucosa oral'),
        ('K13.7', 'Lesão da mucosa oral não especificada'),
    )),
    ('Doenças da língua', (
        ('K14.0', 'Glossite'),
        ('K14.1', 'Língua geográfica'),
        ('K14.2', 'Glossite romboidal mediana'),
        ('K14.3', 'Hipertrofia das papilas linguais'),
        ('K14.4', 'Atrofia das papilas linguais'),
        ('K14.5', 'Língua fissurada'),
        ('K14.6', 'Glossodínia'),
        ('K14.8', 'Outras doenças da língua'),
        ('K14.9', 'Doença da língua não especificada'),
    )),
    ('Traumas e atendimento odontológico', (
        ('S02.5', 'Fratura de dente'),
        ('S03.2', 'Luxação dentária'),
        ('Z01.2', 'Exame odontológico'),
    )),
)


DENTAL_CIDS = tuple(
    DentalCid(code=code, description=description, group=group)
    for group, entries in _GROUPS
    for code, description in entries
)
DENTAL_CID_INDEX = {item.code: item for item in DENTAL_CIDS}


def get_dental_cid_groups():
    return [
        {
            'label': group,
            'items': [DENTAL_CID_INDEX[code] for code, _description in entries],
        }
        for group, entries in _GROUPS
    ]


def get_dental_cid(code):
    return DENTAL_CID_INDEX.get((code or '').strip().upper())


def is_valid_dental_cid(code):
    return bool(get_dental_cid(code))
