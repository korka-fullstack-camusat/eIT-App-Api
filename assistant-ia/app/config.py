"""Configuration du service Assistant IA (variables d'environnement + sources.yaml)."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Claude
    anthropic_api_key: str = ""
    claude_model: str = "claude-opus-5-5"
    claude_effort: str = "medium"  # low | medium | high | xhigh | max
    max_agent_steps: int = 12

    # Sources de données
    sources_file: str = str(BASE_DIR / "sources.yaml")
    sql_max_rows: int = 200
    sql_timeout_ms: int = 15000
    tool_result_max_chars: int = 40000

    # Accès à l'interface : "user1:<hash bcrypt>,user2:<hash bcrypt>"
    # (générer un hash avec : python scripts/hash_password.py)
    assistant_users: str = ""

    # Journal d'audit (questions + requêtes SQL exécutées)
    audit_log_file: str = str(BASE_DIR / "logs" / "audit.jsonl")


class SourceConfig(BaseModel):
    id: str
    name: str
    description: str = ""
    dsn_env: str
    schemas: list[str] = Field(default_factory=lambda: ["public"])
    exclude_tables: list[str] = Field(default_factory=list)  # motifs glob (fnmatch)
    exclude_columns: list[str] = Field(default_factory=list)  # motifs glob (fnmatch)
    hints: str = ""

    @property
    def dsn(self) -> str:
        return os.environ.get(self.dsn_env, "")


class SourcesFile(BaseModel):
    global_exclude_tables: list[str] = Field(default_factory=list)
    global_exclude_columns: list[str] = Field(default_factory=list)
    sources: list[SourceConfig]


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_sources_file() -> SourcesFile:
    path = Path(get_settings().sources_file)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    parsed = SourcesFile.model_validate(data)
    ids = [s.id for s in parsed.sources]
    if len(ids) != len(set(ids)):
        raise ValueError(f"Identifiants de sources en double dans {path}")
    return parsed
