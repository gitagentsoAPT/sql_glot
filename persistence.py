"""Optional MySQL persistence for transpilation audit records."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from transpilation_pipeline import (
    RuleApplication,
    TranspilationTrace,
)

try:
    import pymysql
except ImportError:  # pragma: no cover - exercised in minimal local installs
    pymysql = None


class AuditPersistenceError(RuntimeError):
    """Raised when a trace cannot be written to MySQL."""


class MySQLAuditStore:
    """Persist conversion traces using the four entities from the report."""

    DEFAULT_DIALECTS = {
        "oracle": {"version": None, "supported_options": ["nvl", "oracle_dates"]},
        "mysql": {"version": None, "supported_options": ["ifnull", "backticks"]},
        "postgres": {
            "version": None,
            "supported_options": ["current_date", "double_quoted_identifiers"],
        },
    }

    def __init__(self, connection_factory: Any = None, enabled: bool | None = None) -> None:
        self._connection_factory = connection_factory
        self.enabled = self._resolve_enabled(enabled)

    def _resolve_enabled(self, enabled: bool | None) -> bool:
        if enabled is not None:
            return enabled
        return os.getenv("AUDIT_DB_ENABLED", "false").lower() in {"1", "true", "yes"}

    @classmethod
    def from_env(cls) -> "MySQLAuditStore":
        return cls()

    def persist(self, trace: TranspilationTrace) -> None:
        if not self.enabled:
            return
        if pymysql is None and self._connection_factory is None:
            raise AuditPersistenceError("PyMySQL is not installed.")

        connection = None
        try:
            connection = self._connect()
            with connection.cursor() as cursor:
                self._ensure_seed_data(cursor)
                dialect_ids = self._dialect_ids(cursor)
                rule_ids = self._rule_ids(cursor)
                snapshot_ids = self._insert_snapshots(cursor, trace, dialect_ids)
                self._insert_transformations(cursor, trace, snapshot_ids, rule_ids)
            connection.commit()
        except Exception as exc:
            if connection is not None:
                connection.rollback()
            if isinstance(exc, AuditPersistenceError):
                raise
            raise AuditPersistenceError(str(exc)) from exc
        finally:
            if connection is not None:
                connection.close()

    def _connect(self) -> Any:
        if self._connection_factory is not None:
            return self._connection_factory()
        return pymysql.connect(
            host=os.getenv("MYSQL_HOST", "127.0.0.1"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            user=os.getenv("MYSQL_USER", "sqlglot"),
            password=os.getenv("MYSQL_PASSWORD", "sqlglot"),
            database=os.getenv("MYSQL_DATABASE", "sql_dialect_converter"),
            charset="utf8mb4",
            autocommit=False,
        )

    def _ensure_seed_data(self, cursor: Any) -> None:
        schema_path = Path(__file__).parent / "database" / "schema.sql"
        schema = schema_path.read_text(encoding="utf-8")
        for statement in schema.split(";"):
            statement = statement.strip()
            if statement and not statement.upper().startswith(("CREATE DATABASE", "USE ")):
                cursor.execute(statement)

        for name, details in self.DEFAULT_DIALECTS.items():
            cursor.execute(
                """
                INSERT INTO dialect (dialect_name, version, supported_options)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    version = VALUES(version),
                    supported_options = VALUES(supported_options)
                """,
                (name, details["version"], json.dumps(details["supported_options"])),
            )

        for rule in TranspilationTrace.rule_definitions():
            cursor.execute(
                """
                INSERT INTO optimization_rule
                    (rule_name, pass_number, description, is_active)
                VALUES (%s, %s, %s, TRUE)
                ON DUPLICATE KEY UPDATE
                    pass_number = VALUES(pass_number),
                    description = VALUES(description),
                    is_active = TRUE
                """,
                (rule.name, rule.pass_number, rule.description),
            )

    def _dialect_ids(self, cursor: Any) -> dict[str, int]:
        cursor.execute("SELECT dialect_id, dialect_name FROM dialect")
        return {name: int(identifier) for identifier, name in cursor.fetchall()}

    def _rule_ids(self, cursor: Any) -> dict[str, int]:
        cursor.execute("SELECT rule_id, rule_name FROM optimization_rule")
        return {name: int(identifier) for identifier, name in cursor.fetchall()}

    def _insert_snapshots(
        self,
        cursor: Any,
        trace: TranspilationTrace,
        dialect_ids: dict[str, int],
    ) -> dict[int, int]:
        snapshot_ids: dict[int, int] = {}
        for snapshot in trace.snapshots:
            cursor.execute(
                """
                INSERT INTO ast_snapshot
                    (request_id, source_dialect_id, target_dialect_id,
                     snapshot_stage, stage_number, raw_sql, generated_sql,
                     ast_json, node_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    trace.request_id,
                    dialect_ids[trace.source_dialect],
                    dialect_ids[trace.target_dialect],
                    snapshot.stage,
                    snapshot.stage_number,
                    trace.raw_sql,
                    snapshot.generated_sql,
                    json.dumps(snapshot.ast_json),
                    snapshot.node_count,
                ),
            )
            snapshot_ids[snapshot.stage_number] = int(cursor.lastrowid)
        return snapshot_ids

    def _insert_transformations(
        self,
        cursor: Any,
        trace: TranspilationTrace,
        snapshot_ids: dict[int, int],
        rule_ids: dict[str, int],
    ) -> None:
        for transformation in trace.transformations:
            cursor.execute(
                """
                INSERT INTO transformation
                    (snapshot_id, step_number, rule_id, output_snapshot_id,
                     ast_delta, exec_time_us)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    snapshot_ids[transformation.input_stage_number],
                    transformation.step_number,
                    rule_ids[transformation.rule_name],
                    snapshot_ids[transformation.output_stage_number],
                    json.dumps(transformation.ast_delta),
                    transformation.exec_time_us,
                ),
            )
