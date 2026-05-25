"""
Módulo de diagnóstico periodontal clínico.
Implementa a classificação AAP 2018 para Estágio e Grau de Periodontite.
Extraído de blueprints/exams.py para separar lógica clínica da camada HTTP.
"""
import json
import re


def determinar_grau_periodontal(anamnese_dict):
    """
    Analisa os dados em texto da Anamnese via Expressões Regulares (RegEx) 
    para modular a taxa de progressão da doença Periodontal (Grau A, B ou C)
    segundo os fatores de risco primários da AAP 2018 (Diabetes e Tabagismo).
    """
    # Fallback inicial
    grau = "Grau B"
    justificativa_grau = ""
    
    # Textos da anamnese para varredura
    anamnese_texto = str(anamnese_dict).lower()
    explica_doenca = (anamnese_dict.get('sofre_doenca_explica') or "").lower()
    
    # Extratores Estruturados
    fuma = anamnese_dict.get('fuma') == 'Sim'
    fuma_qtd = 0
    try: 
        fuma_qtd = int(anamnese_dict.get('fuma_quantidade', 0))
    except: 
        pass

    # Gatilhos RegEx C (Agravamento Máximo)
    # Busca por HbA1c numérico solto no texto (ex: "hba1c 7.5", "hba1c: 8,2")
    hba1c_match = re.search(r'hba1c.*?(\d+[\.,]\d+|\d+)', anamnese_texto)
    hba1c_val = 0.0
    if hba1c_match:
        try:
            hba1c_val = float(hba1c_match.group(1).replace(',', '.'))
        except: pass

    # Análise de Grau C (10+ cigarros OU HbA1c >= 7.0%)
    if (fuma and fuma_qtd >= 10):
        grau = "Grau C"
        justificativa_grau = f"Grau C definido devido a tabagismo reportado ({fuma_qtd} cigarros/dia)."
    elif hba1c_val >= 7.0:
        grau = "Grau C"
        justificativa_grau = f"Grau C definido devido a diabetes não controlada detectada no histórico (HbA1c = {hba1c_val}%)."
    elif 'hba1c >= 7' in anamnese_texto:
        grau = "Grau C"
        justificativa_grau = "Grau C definido devido a diabetes não controlada detectada no histórico (HbA1c \u2265 7%)."
        
    # Análise de Grau A (Paciente estritamente Limpo de Fatores)
    elif not fuma and "diabet" not in anamnese_texto:
        grau = "Grau A"

    return grau, justificativa_grau


def calculate_periograma_diagnosis(medicoes_data, anamnesis):
    try:
        medicoes = json.loads(medicoes_data) if isinstance(medicoes_data, str) else medicoes_data
    except:
        return "", ""

    max_interproximal_pic = 0
    max_pic_tooth = ""
    max_ps = 0
    max_ps_tooth = ""
    
    has_furca_2_or_3 = False
    furca_trigger_tooth = ""
    has_mobilidade_2_or_3 = False
    mobilidade_trigger_tooth = ""
    
    affected_teeth_by_periodontitis = set()
    teeth_matching_final_stage = set()
    present_teeth = set()
    ss_active = 0
    total_sites = 0

    for tooth, data in medicoes.items():
        if not isinstance(data, dict):
            continue

        if data.get('sitios') or 'mobilidade' in data or 'furca' in data:
            present_teeth.add(tooth)
            
        try:
            furca_int = int(data.get('furca', 0))
            if furca_int >= 2:
                has_furca_2_or_3 = True
                furca_trigger_tooth = tooth
                teeth_matching_final_stage.add(tooth)
        except: pass

        try:
            mob_int = int(data.get('mobilidade', 0))
            if mob_int >= 2:
                has_mobilidade_2_or_3 = True
                mobilidade_trigger_tooth = tooth
                teeth_matching_final_stage.add(tooth)
        except: pass

        sitios = data.get('sitios', {})
        for metric_key, val in sitios.items():
            if not val and val is not True: continue
            parts = metric_key.split('_')
            if len(parts) < 4: continue
            
            metric = parts[0]
            pos = parts[3]

            if metric == 'ss' and val is True:
                total_sites += 1
                ss_active += 1
                continue
                
            if metric == 'ps':
                total_sites += 1
                try: 
                    val_int = int(val)
                    if val_int > max_ps: 
                        max_ps = val_int
                        max_ps_tooth = tooth
                    if val_int >= 5:
                        teeth_matching_final_stage.add(tooth)
                except: pass
                
            if metric == 'nci':
                try:
                    val_int = int(val)
                    if pos in ['d', 'mes']:
                        if val_int > max_interproximal_pic:
                            max_interproximal_pic = val_int
                            max_pic_tooth = tooth
                        if val_int >= 1:
                            affected_teeth_by_periodontitis.add(tooth)
                            teeth_matching_final_stage.add(tooth)
                except: pass

    if total_sites == 0:
        total_sites = len(present_teeth) * 6 if present_teeth else 32 * 6
    ss_val = (ss_active / total_sites) * 100 if total_sites > 0 else 0

    is_periodontitis = (max_interproximal_pic >= 1) or has_mobilidade_2_or_3 or has_furca_2_or_3 or (max_ps >= 5)

    anamnesis_dict = dict(anamnesis) if anamnesis else {}
    anamnesis_text = str(anamnesis_dict).lower()

    if is_periodontitis:
        if max_interproximal_pic >= 5:
            estagio_base = 3
        elif max_interproximal_pic >= 3:
            estagio_base = 2
        else:
            estagio_base = 1

        estagio_final = estagio_base
        modificadores_msg = []

        if has_mobilidade_2_or_3:
            if 4 > estagio_final:
                estagio_final = 4
                modificadores_msg.append(f"Mobilidade \u2265 2 no dente {mobilidade_trigger_tooth} elevou a categoria")
            elif estagio_final == 4 and not modificadores_msg:
                 modificadores_msg.append(f"agravo co-existente: Mobilidade \u2265 2 (dente {mobilidade_trigger_tooth})")

        if has_furca_2_or_3:
            if 3 > estagio_final:
                estagio_final = 3
                modificadores_msg.append(f"Furca grau 2 ou 3 no dente {furca_trigger_tooth} elevou a categoria")
            elif estagio_final >= 3 and not modificadores_msg:
                 modificadores_msg.append(f"agravo co-existente: Furca avançada (dente {furca_trigger_tooth})")
            
        if max_ps >= 6:
            if 3 > estagio_final:
                estagio_final = 3
                modificadores_msg.append(f"PS de {max_ps}mm no dente {max_ps_tooth} elevou a categoria")
            elif estagio_final >= 3 and not modificadores_msg:
                 modificadores_msg.append(f"agravo co-existente: PS Grave de {max_ps}mm (dente {max_ps_tooth})")
            
        if max_ps == 5:
            if 2 > estagio_final:
                estagio_final = 2
                modificadores_msg.append(f"PS de 5mm no dente {max_ps_tooth} elevou a categoria")
            elif estagio_final >= 2 and not modificadores_msg:
                 modificadores_msg.append(f"agravo co-existente: PS de 5mm (dente {max_ps_tooth})")

        numbers = [int(s) for s in re.findall(r'\b\d+\b', anamnesis_text)]
        perda_5_mais = any(n >= 5 for n in numbers) and ("perda" in anamnesis_text or "perdi" in anamnesis_text or "perdidos" in anamnesis_text)
        if perda_5_mais:
            if 4 > estagio_final:
                estagio_final = 4
                modificadores_msg.append("Anamnese indicou perda \u2265 5 dentes elevando a categoria")

        estagio_str = ["I", "II", "III", "IV"][estagio_final - 1]

        num_present = len(present_teeth) if present_teeth else 32
        ratio = len(teeth_matching_final_stage) / num_present if num_present > 0 else 0
        perc_afetado = ratio * 100
        extensao = "Generalizada" if perc_afetado >= 30 else "Localizada"

        grau, justificativa_grau = determinar_grau_periodontal(anamnesis_dict)

        final_diag = f"DIAGNÓSTICO: Periodontite Estágio {estagio_str}, {extensao}, {grau}."
        
        justificativa_texto = f"Diagnóstico definido por PIC máximo de {max_interproximal_pic}mm." if max_interproximal_pic > 0 else "Diagnóstico ancorado por alta severidade clínica."
        if modificadores_msg and estagio_final > estagio_base:
            joined_mods = ", ".join(modificadores_msg)
            justificativa_texto = f"{justificativa_texto} Modificado para Estágio {estagio_str} devido a: {joined_mods}."
        elif modificadores_msg:
            joined_mods = ", ".join(modificadores_msg)
            justificativa_texto = f"{justificativa_texto} Constatado também {joined_mods}."
        
        justificativa = f"JUSTIFICATIVA: {justificativa_texto} Afeta {int(perc_afetado)}% ({len(teeth_matching_final_stage)} de {num_present}) dos dentes presentes."
        
        if justificativa_grau:
            justificativa += f" {justificativa_grau}"

    else:
        if ss_val >= 10:
            ext = "Generalizada" if ss_val >= 30 else "Localizada"
            final_diag = f"DIAGNÓSTICO: Gengivite Induzida por Biofilme {ext}."
            justificativa = f"JUSTIFICATIVA: Índice de sangramento SS ({ss_val:.1f}%) \u2265 10% com ausência absoluta de perda de inserção clínica (PIC=0) ou parâmetros de periodontite."
        else:
            final_diag = "DIAGNÓSTICO: Saúde Periodontal Clínica."
            justificativa = f"JUSTIFICATIVA: SS ({ss_val:.1f}%) < 10% e ausência de perda de inserção interproximal significativa (PIC=0)."

    return final_diag, justificativa
