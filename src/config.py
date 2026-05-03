from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "variant_response.duckdb"
GDSC_SEED_PATH = DATA_DIR / "gdsc_seed.csv"
LITERATURE_SEED_PATH = DATA_DIR / "literature_seed.csv"
HGNC_PROTEIN_CODING_PATH = DATA_DIR / "hgnc_protein_coding_genes.csv"
DRUG_OPTIONS_PATH = DATA_DIR / "drug_options.csv"
CANCER_OPTIONS_PATH = DATA_DIR / "cancer_type_options.csv"

CIVIC_GRAPHQL_URL = "https://civicdb.org/api/graphql"
CIVIC_CACHE_TTL_HOURS = 24 * 7
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-4-6"

DEFAULT_PAGE_SIZE = 100

PROFILE_MATCH_SCORES = {
    "exact": 4,
    "grouped": 3,
    "gene_only": 2,
    "none": 0,
}

THERAPY_MATCH_SCORES = {
    "exact": 3,
    "class": 2,
    "partial": 1,
    "none": 0,
}

CANCER_MATCH_SCORES = {
    "exact": 3,
    "related": 2,
    "broad": 1,
    "none": 0,
}
