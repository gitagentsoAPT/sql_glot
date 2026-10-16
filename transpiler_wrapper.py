"""Structured SQL dialect conversion built on top of sqlglot."""

from __future__ import annotations

from typing import Literal, TypedDict

from sqlglot import transpile
from sqlglot.errors import ErrorLevel, ParseError, SqlglotError, UnsupportedError


ErrorCategory = Literal["validation", "conversion", "internal"]


class SQLTranspilationResult(TypedDict):
    """Dictionary contract returned by ``SQLTranspilationEngine``."""

    success: bool
    converted_sql: str | None
    error_message: str | None
    error_category: ErrorCategory | None


class SQLTranspilationEngine:
    """Validates and converts SQL among the application's supported dialects."""

    def __init__(self) -> None:
        """Configure the sqlglot dialect identifiers accepted by this engine."""
        self.supported_dialects = frozenset({"mysql", "postgres", "oracle"})

    def transpile_query(
        self,
        query: str,
        source_dialect: str,
        target_dialect: str,
    ) -> SQLTranspilationResult:
        """Convert a query to a target dialect and return a structured result."""
        validation_error = self._validate_request(
            query, source_dialect, target_dialect
        )
        if validation_error:
            return {
                "success": False,
                "converted_sql": None,
                "error_message": validation_error,
                "error_category": "validation",
            }

        try:
            converted_sql = "\n\n".join(
                transpile(
                    query.strip(),
                    read=source_dialect,
                    write=target_dialect,
                    error_level=ErrorLevel.RAISE,
                    pretty=True,
                )
            )
        except (ParseError, UnsupportedError, SqlglotError, ValueError) as exc:
            return {
                "success": False,
                "converted_sql": None,
                "error_message": f"Unable to convert this SQL: {exc}",
                "error_category": "conversion",
            }
        except Exception:
            return {
                "success": False,
                "converted_sql": None,
                "error_message": "An unexpected error occurred while converting the SQL.",
                "error_category": "internal",
            }

        return {
            "success": True,
            "converted_sql": converted_sql,
            "error_message": None,
            "error_category": None,
        }

    def _validate_request(
        self,
        query: str,
        source_dialect: str,
        target_dialect: str,
    ) -> str | None:
        """Return a validation message, or ``None`` when the request is valid."""
        if not isinstance(query, str):
            return "source_sql must be a string."
        if not isinstance(source_dialect, str) or not isinstance(target_dialect, str):
            return "Source and target dialects must be strings."
        if not query.strip():
            return "Enter a SQL query to convert."
        if (
            source_dialect not in self.supported_dialects
            or target_dialect not in self.supported_dialects
        ):
            return "Choose a supported source and target dialect."
        return None
