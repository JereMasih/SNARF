from snarf.executive.opinion import ExecutiveOpinion, parse_opinions


def test_parses_headline_and_claims():
    text = (
        "HEADLINE: El proyecto va bien.\n"
        "---\n"
        "CLAIM: Hay 3 proyectos activos | BASIS: hecho | FUENTE: project_list\n"
        "CLAIM: Conviene priorizar el primero | BASIS: opinión | FUENTE: \n"
    )
    headline, opinions = parse_opinions(text, tools_actually_called={"project_list"})
    assert headline == "El proyecto va bien."
    assert opinions == [
        ExecutiveOpinion(claim="Hay 3 proyectos activos", basis="hecho", source="project_list"),
        ExecutiveOpinion(claim="Conviene priorizar el primero", basis="opinión", source=None),
    ]


def test_hecho_without_a_real_source_degrades_to_inferencia():
    text = (
        "HEADLINE: x\n"
        "---\n"
        "CLAIM: Todo funciona perfecto | BASIS: hecho | FUENTE: project_list\n"
    )
    # El rol dice haber usado project_list pero el tool_handler nunca lo vio
    # llamado de verdad este turno — se degrada, nunca se confía en el
    # self-report del modelo.
    headline, opinions = parse_opinions(text, tools_actually_called=set())
    assert opinions[0].basis == "inferencia"


def test_hecho_with_empty_source_degrades_to_inferencia():
    text = "HEADLINE: x\n---\nCLAIM: algo real | BASIS: hecho | FUENTE: \n"
    _, opinions = parse_opinions(text, tools_actually_called=set())
    assert opinions[0].basis == "inferencia"


def test_unknown_basis_value_falls_back_to_opinion():
    text = "HEADLINE: x\n---\nCLAIM: algo | BASIS: creencia_firme | FUENTE: \n"
    _, opinions = parse_opinions(text, tools_actually_called=set())
    assert opinions[0].basis == "opinión"


def test_missing_separator_yields_no_opinions_but_keeps_headline():
    text = "HEADLINE: solo esto, sin separador"
    headline, opinions = parse_opinions(text, tools_actually_called=set())
    assert headline == "solo esto, sin separador"
    assert opinions == []


def test_missing_headline_falls_back_to_default_text():
    text = "---\nCLAIM: algo | BASIS: opinión | FUENTE: \n"
    headline, _ = parse_opinions(text, tools_actually_called=set())
    assert headline == "Sin postura clara."


def test_malformed_claim_lines_are_skipped_without_crashing():
    text = "HEADLINE: x\n---\nesto no tiene el formato pedido\nCLAIM: bien | BASIS: hecho | FUENTE: t\n"
    _, opinions = parse_opinions(text, tools_actually_called={"t"})
    assert len(opinions) == 1
    assert opinions[0].claim == "bien"


def test_source_matching_is_exact_not_substring():
    # Un rol que escribe una fuente parecida pero no exacta a un tool
    # realmente llamado no puede quedarse con basis='hecho' — evita que un
    # nombre parecido "cuele" como si fuera una fuente real verificada.
    text = "HEADLINE: x\n---\nCLAIM: algo | BASIS: hecho | FUENTE: project_lista\n"
    _, opinions = parse_opinions(text, tools_actually_called={"project_list"})
    assert opinions[0].basis == "inferencia"
