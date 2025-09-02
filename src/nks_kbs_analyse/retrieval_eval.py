"""Hjelpefunksjoner for å beregne evalueringsmetrikker for søk i vektordatabasen med kunnskapsartikler."""

import datetime as dt
import timeit
from typing import TypedDict, Union

import pandas as pd
from google.cloud import bigquery
from google.cloud.bigquery.table import Row

from nks_kbs_analyse.knowledgebase import get_column_metadata
from nks_kbs_analyse.retriever import NKSRetriever

# Konfig for hvor vi skriver evalueringsresultatene (optional)
bq_client = bigquery.Client("nks-aiautomatisering-prod-194a")
table_id = "nks-aiautomatisering-prod-194a.kunnskapsbase.vdb_benchmarking"
tab_schema = [
    bigquery.SchemaField("fts_weight", bigquery.enums.SqlTypeNames.FLOAT64),
    bigquery.SchemaField("semantic_weight", bigquery.enums.SqlTypeNames.FLOAT64),
    bigquery.SchemaField("knowledge_column", bigquery.enums.SqlTypeNames.STRING),
    bigquery.SchemaField("k", bigquery.enums.SqlTypeNames.INT64),
    bigquery.SchemaField("question_id", bigquery.enums.SqlTypeNames.STRING),
    bigquery.SchemaField("hit_rate_article", bigquery.enums.SqlTypeNames.FLOAT64),
    bigquery.SchemaField("hit_rate_section", bigquery.enums.SqlTypeNames.FLOAT64),
    bigquery.SchemaField(
        "hit_rate_section_custom", bigquery.enums.SqlTypeNames.FLOAT64
    ),
    bigquery.SchemaField(
        "reciprocal_rank_article", bigquery.enums.SqlTypeNames.FLOAT64
    ),
    bigquery.SchemaField(
        "reciprocal_rank_section", bigquery.enums.SqlTypeNames.FLOAT64
    ),
    bigquery.SchemaField("execution_time", bigquery.enums.SqlTypeNames.FLOAT64),
    bigquery.SchemaField("evaluation_timestamp", bigquery.enums.SqlTypeNames.DATETIME),
]

job_config = bigquery.LoadJobConfig(
    schema=tab_schema,
    write_disposition="WRITE_APPEND",
)


def dytt_data_til_bigquery(df: pd.DataFrame, table_id: str) -> None:
    """Skriver data til BigQuery tabell."""
    job = bq_client.load_table_from_dataframe(df, table_id, job_config=job_config)
    job.result()
    print(f"  {len(df)} rader skrevet til tabell")


# Evalueringsmetrikker


def hit_rate(
    expected_ids: Union[list[str], list[tuple[str, str, str]]],
    retrieved_ids: Union[list[str], list[tuple[str, str, str]]],
    k: int | None = None,
) -> float:
    """Beregner hit rate for ett enkelt query-resultat.

    (Sjekker om fasiten er blant de returnerte resultatene)

    Args:
        expected_ids (list[str | tuple[str,str, str]]):
            'Fasit' for casen. Enten liste med artikkelID eller med tuple av
            artikkelID, tab og seksjon.
        retrieved_ids (list[str | tuple[str,str,str]]):
            Søkeresultat for casen.  Enten liste med artikkelID eller med tuple
            av artikkelID, tab og seksjon.
        k (Optional(int)):
            Hvor mange av de returnerte treffene som skal brukes i vurderingen.
            Hvis ikke spesifisert brukes alle.

    Returns:
        hit rate (0.0 eller 1.0)

    """
    if k is not None and k > len(retrieved_ids):
        raise ValueError(
            "k cannot be greater than the number of items in retrieved_ids"
        )

    if k is None:
        k = len(retrieved_ids)

    is_hit = any(id in expected_ids for id in retrieved_ids[:k])

    return 1.0 if is_hit else 0.0


def hit_rate_custom(
    expected_ids: list[tuple[str, str, str]],
    retrieved_ids: list[tuple[str, str, str]],
    k: int | None = None,
) -> float:
    """Beregner custom versjon av hit rate for ett enkelt query-resultat.

    Denne varianten er ikke bare binær 0/1, men den vil gi 0.5 poeng for
    tilfeller med riktig artikkel, men feil seksjon.

    Args:
        expected_ids (list[tuple[str,str, str]]):
            'Fasit' for casen. Liste med tuple av artikkelID, tab og seksjon
        retrieved_ids (list[tuple[str,str, str]]):
            Søkeresultat for casen.  Liste med tuple av artikkelID,tab og seksjon
        k (Optional(int)):
            Hvor mange av de returnerte treffene som skal brukes i vurderingen.
            Hvis ikke spesifisert brukes alle.

    Returns:
        hit rate (0.0, 0.5 eller 1.0)

    """
    if k is not None and k > len(retrieved_ids):
        raise ValueError(
            "k cannot be greater than the number of items in retrieved_ids"
        )

    if k is None:
        k = len(retrieved_ids)

    # trekker ut artikkelIDer fra tuple
    expected_article_ids = [id[0] for id in expected_ids]
    retrieved_article_ids = [id[0] for id in retrieved_ids]

    if any(id in expected_ids for id in retrieved_ids[:k]):
        # funnet riktig artikkel, tab og seksjon
        return 1.0
    elif any(id in expected_article_ids for id in retrieved_article_ids[:k]):
        # funnet riktig artikkel, men traff ikke på tab+seksjon
        return 0.5
    else:
        # riktig artikkel ikke funnet
        return 0.0


def reciprocal_rank(
    expected_ids: Union[list[str], list[tuple[str, str, str]]],
    retrieved_ids: Union[list[str], list[tuple[str, str, str]]],
    k: int | None = None,
) -> float:
    """Beregner reciprocal rank for ett enkelt query resultat.

    (Sjekker hva som er ranken på første treff som tilsvarer fasit.)

    Args:
        expected_ids (list[str | tuple[str,str,str]]):
            'Fasit' for casen. Enten liste med artikkelID eller med tuple av
            artikkelID,tab og seksjon.
        retrieved_ids (list[str | tuple[str,str,str]]):
            Søkeresultat for casen.  Enten liste med artikkelID eller med tuple
            av artikkelID,tab og seksjon.
        k (Optional(int)):
            Hvor mange av de returnerte treffene som skal brukes i vurderingen.
            Hvis ikke spesifisert brukes alle.

    Returns:
        reciprocal rank (tall mellom 0.0 og 1.0)
    """
    if k is not None and k > len(retrieved_ids):
        raise ValueError(
            "k cannot be greater than the number of items in retrieved_ids"
        )

    if k is None:
        k = len(retrieved_ids)

    for i, id in enumerate(retrieved_ids[:k]):
        if id in expected_ids:
            return 1.0 / (i + 1)

    return 0.0


# Hjelpefunksjoner for å kjøre søk og strukturere resultatene
def retrieval_for_single_case(
    vector_store: NKSRetriever,
    question: str,
    k: int,
    fts_weight: float,
    semantic_weight: float,
) -> list[tuple[str, str, str, float, float]]:
    """Gjør retrieval av top k dokumenter fra en vektorbase basert på et input question.

    Args:
        vector_store (NKSRetriever):
            Vektorbase som skal benyttes for søket (instans av PGVector via nks_vdb)
        question (str):
            Query som skal brukes for å finne lignende dokumenter
        k (int):
            (max) antall dokumenter som skal returneres
        fts_weight (float):
            Vekten som tekstsøket skal tillegges
        semantic_weight (float):
            Vekten som vektorsøket skal tillegges

    Returns:
        Liste med tupler av artikkelid, tab, seksjon, similarity og score [str, str, str, float, float]
    """
    # Validering av input
    if not isinstance(question, str):
        raise TypeError("question må være en string")
    if not isinstance(k, int) or k <= 0:
        raise ValueError("k må være en positiv integer")
    if not isinstance(
        vector_store,
        (NKSRetriever,),
    ):
        raise TypeError("vector_store må være en NKSRetriever-instans")

    retrieved_docs_and_scores = vector_store.invoke(
        question, k=k, fts_weight=fts_weight, semantic_weight=semantic_weight
    )
    retrieved_doc_ids_and_scores = [
        (
            doc.metadata["KnowledgeArticleId"],
            doc.metadata["Tab"],
            doc.metadata["Section"],
            doc.metadata["SemanticSimilarity"],
            doc.metadata["Score"],
        )
        for doc in retrieved_docs_and_scores
    ]
    return retrieved_doc_ids_and_scores


class RetrievalResult(TypedDict):
    """TypedDict som angir strukturen i et retrieval_result."""

    question_id: str
    knowledge_column: str
    expected_docs: list[tuple[str, str, str]]
    retrieved_doc_ids_and_scores: list[tuple[str, str, str, float, float]]
    total_time: float


def restructure_retrieval_result(
    question_id: str,
    knownledge_column: str,
    true_doc_id: tuple[str, str, str],
    retrieved_doc_ids_and_scores: list[tuple[str, str, str, float, float]],
    total_time: float,
) -> RetrievalResult:
    """Hjelpefunksjon for å restrukturere output fra retrieval_for_single_case.

    Obs - forventer per nå at det kun er én korrekt artikkelseksjon per spørsmål

    Args:
        question_id (str):
            Unik ID for spørsmålet
        knownledge_column (str):
            Kolonnenavn i kunnskapsbasen som spørsmålet er hentet fra
        true_doc_id (tuple[str, str, str]):
            ArtikkelID og seksjon for fasiten
        retrieved_doc_ids_and_scores (list[tuple[str, str, str,float, float]]):
            Liste med tupler av artikkelid, tab,seksjon og likhets-scores
        total_time (float):
            Tid brukt på søket

    Returns:
        Dict med spørsmåls-id, fasit, søkeresultater og tid brukt
    """
    expected_docs = [true_doc_id]

    return {
        "question_id": question_id,
        "knowledge_column": knownledge_column,
        "expected_docs": expected_docs,
        "retrieved_doc_ids_and_scores": retrieved_doc_ids_and_scores,
        "total_time": total_time,
    }


def run_retrieval_for_cases(
    vector_store: NKSRetriever,
    cases: list[Row],
    k: int,
    fts_weight: float,
    semantic_weight: float,
) -> list[RetrievalResult]:
    """For hver query i cases, hent topp k dokumenter fra angitt vektordatabase.

    Args:
        vector_store (NKSRetriever):
            Vektorbase som skal benyttes for søket (instans av PGVector via nks_vdb)
        cases (list[Row]):
            Liste med testcaser fra BigQuery.
        k (int):
            (max) antall dokumenter som skal returneres
        fts_weight (float):
            Vekten som tekstsøket skal tillegges
        semantic_weight (float):
            Vekten som vektorsøket skal tillegges

    Returns:
        Liste som for hver testcase angir fasit (artikkelID, tab, seksjon) samt
        (artikkelID, tab, seksjon, similarity, score) på alle
        artikkelIDene som ble hentet.
    """
    result_per_case = []
    for i, row in enumerate(cases):
        start = timeit.default_timer()
        retrieved_doc_ids_and_scores = retrieval_for_single_case(
            vector_store,
            row["question"],
            k=k,
            fts_weight=fts_weight,
            semantic_weight=semantic_weight,
        )
        total_time = timeit.default_timer() - start

        # mapper om kolonnenavnene til feltnavn benyttet i vektordatabasene
        tab_and_section = get_column_metadata(
            row["knowledge_column"], row["ArticleType"], row["Title"]
        )
        tab = tab_and_section["Tab"]
        section = tab_and_section["Section"]

        if section is None:
            raise ValueError(
                f"No mapping found for knowledge_column: {row['knowledge_column']}"
            )

        results = restructure_retrieval_result(
            row["id"],
            row["knowledge_column"],
            (row["knowledge_article_id"], tab, section),
            retrieved_doc_ids_and_scores,
            total_time,
        )

        result_per_case.append(results)

    return result_per_case


def compute_retrieval_metrics(
    results: list[RetrievalResult], k: int | None = None
) -> pd.DataFrame:
    """Beregn evalueringsmetrikker for resultatene fra run_retrieval_for_cases.

    Finner i tillegg max score for høyest rangerte relevante dokument og
    max score for høyest rangerte irrelevante dokument.

    Args:
        results (list[RetrievalResult]):
            Output fra run_retrieval_for_cases
        k (int):
            Antall returnerte dokumenter som skal inngå i evalueringen.

    Returns:
        DataFrame med evalueringsmetrikker per case for angitt k
    """
    question_ids = []
    knowledge_columns = []
    execution_times = []

    hit_rates_article = []
    reciprocal_ranks_article = []

    hit_rates_section = []
    hit_rates_section_custom = []
    reciprocal_ranks_section = []

    for item in results:
        question_ids.append(item["question_id"])
        knowledge_columns.append(item["knowledge_column"])
        execution_times.append(item["total_time"])

        expected_article_ids = [id for id, tab, section in item["expected_docs"]]
        retrieved_article_ids = [
            id
            for id, tab, section, similarity, score in item[
                "retrieved_doc_ids_and_scores"
            ]
        ]

        hit_rates_article.append(
            hit_rate(expected_article_ids, retrieved_article_ids, k)
        )
        reciprocal_ranks_article.append(
            reciprocal_rank(expected_article_ids, retrieved_article_ids, k)
        )

        expected_section_ids = item["expected_docs"]
        retrieved_section_ids = [
            (id, tab, section)
            for id, tab, section, similarity, score in item[
                "retrieved_doc_ids_and_scores"
            ]
        ]

        hit_rates_section.append(
            hit_rate(expected_section_ids, retrieved_section_ids, k)
        )
        hit_rates_section_custom.append(
            hit_rate_custom(expected_section_ids, retrieved_section_ids, k)
        )
        reciprocal_ranks_section.append(
            reciprocal_rank(expected_section_ids, retrieved_section_ids, k)
        )

    metrics_per_case_dict = {
        "question_id": question_ids,
        "knowledge_column": knowledge_columns,
        "hit_rate_article": hit_rates_article,
        "hit_rate_section": hit_rates_section,
        "hit_rate_section_custom": hit_rates_section_custom,
        "reciprocal_rank_article": reciprocal_ranks_article,
        "reciprocal_rank_section": reciprocal_ranks_section,
        "execution_time": execution_times,
    }

    metrics_per_case_df = pd.DataFrame(metrics_per_case_dict)

    # legg på info om hvilken k-verdi metrikkene ble beregnet på
    metrics_per_case_df.insert(0, "k", k)

    return metrics_per_case_df


def agg_retrieval_results(
    metrics_per_case_df: pd.DataFrame,
    group_cols: list[str] = ["fts_weight", "semantic_weight", "knowledge_column", "k"],
) -> pd.DataFrame:
    """Aggregerer evalueringsmetrikker per case til gjennomsnittsverdier per søkekonfigurasjon."""
    metrics_agg_df = (
        metrics_per_case_df.groupby(group_cols)
        .agg(
            {
                "hit_rate_article": "mean",
                "hit_rate_section": "mean",
                "hit_rate_section_custom": "mean",
                "reciprocal_rank_article": "mean",
                "reciprocal_rank_section": "mean",
                "execution_time": "mean",
            }
        )
        .reset_index()
    )

    # Renaming av kolonner
    metrics_agg_df.columns = group_cols + [
        "mean_hit_rate_article",
        "mean_hit_rate_section",
        "mean_hit_rate_section_custom",
        "mean_reciprocal_rank_article",
        "mean_reciprocal_rank_section",
        "mean_execution_time",
    ]

    return metrics_agg_df


def run_evaluations(
    vector_store: NKSRetriever,
    cases: list[Row],
    k: int,
    fts_weight: float,
    semantic_weight: float,
    write_results_to_bq: bool = True,
    group_cols: list[str] = ["fts_weight", "semantic_weight", "knowledge_column", "k"],
) -> pd.DataFrame:
    """Funksjon for å utføre søk og evaluere resultater for en liste med testcaser.

    Tar vare på resultatene for alle k-verdier opptil angitt k

    Args:
        vector_store (NKSRetriever):
            Vektorbase som skal benyttes for søket (instans av PGVector via nks_vdb)
        cases (list[Row]):
            Liste med testcaser fra BigQuery.
        k (int):
            (max) antall dokumenter som skal returneres
        fts_weight (float):
            Vekten som tekstsøket skal tillegges
        semantic_weight (float):
            Vekten som vektorsøket skal tillegges
        write_results_to_bq (bool):
            Hvis True skrives resultatmetrikkene per case til BigQuery
        group_cols (list[str]):
            Kolonner evalueringsresultatene skal aggregeres på

    Returns:
        DataFrame med evalueringsmetrikker for alle k-verdier fra 1 til k

    """
    metrics_per_case: Union[list[pd.DataFrame], pd.DataFrame] = []
    for k_val in range(1, k + 1):
        results_per_case_at_k = run_retrieval_for_cases(
            vector_store, cases, k_val, fts_weight, semantic_weight
        )
        metrics_per_case_at_k = compute_retrieval_metrics(results_per_case_at_k, k_val)

        # legg på info om hvilken type søk som ble benyttet
        metrics_per_case_at_k.insert(0, "semantic_weight", semantic_weight)
        metrics_per_case_at_k.insert(0, "fts_weight", fts_weight)

        metrics_per_case.append(metrics_per_case_at_k)

    metrics_per_case = pd.concat(metrics_per_case)

    if write_results_to_bq:
        # legger til tidspunkt for evalueringen før vi skriver til BigQuery
        metrics_per_case["evaluation_timestamp"] = dt.datetime.now()
        dytt_data_til_bigquery(metrics_per_case, table_id)

    # beregner gjennomsnittsverdier for evalueringsmetrikkene
    metrics_agg = agg_retrieval_results(metrics_per_case, group_cols)

    return metrics_agg
