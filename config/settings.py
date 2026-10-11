"""
Central configuration for GraphRAG-Net.
Loads from environment variables (.env) with sane local-dev defaults.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

for d in (RAW_DIR, PROCESSED_DIR):
    d.mkdir(parents=True, exist_ok=True)

# --- Neo4j ---
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "graphrag_dev_pw")

# --- Data sources ---
ATTACK_STIX_URL = (
    "https://raw.githubusercontent.com/mitre-attack/attack-stix-data/"
    "master/enterprise-attack/enterprise-attack.json"
)

NVD_CVE_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"
CAPEC_STIX_URL = "https://raw.githubusercontent.com/mitre/cti/master/capec/2.1/stix-capec.json"
CWE_JSON_URL = "https://raw.githubusercontent.com/lirantal/cwe-sdk/master/raw/cwe-archive.json"

# --- LLM (Groq API) ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Active Groq models (Updated for Groq's high-speed reasoning endpoints)
GROQ_MODEL = "openai/gpt-oss-120b"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GITHUB_ADVISORIES_API = "https://api.github.com/advisories"
