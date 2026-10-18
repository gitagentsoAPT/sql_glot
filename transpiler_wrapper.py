"""Structured SQL dialect conversion built on top of sqlglot."""

from __future__ import annotations

from typing import Literal, TypedDict

from sqlglot.errors import ParseError, SqlglotError, UnsupportedError

from transpilation_pipeline import (
    TranspilationPipeline,
    TranspilationPipelineError,
)


ErrorCategory = Literal["validation", "conversion", "internal"]


class SQLTranspilationResult(TypedDict):
    """Dictionary contract returned by ``SQLTranspilationEngine``."""

    success: bool
    converted_sql: str | None
    error_message: str | None
    error_category: ErrorCategory | None
    error_stage: str | None
    trace: dict[str, object] | None


class SQLTranspilationEngine:
    """Validates and converts SQL among the application's supported dialects."""

    def __init__(self) -> None:
        """Configure the sqlglot dialect identifiers accepted by this engine."""
        self.supported_dialects = frozenset({"mysql", "postgres", "oracle"})
        self.pipeline = TranspilationPipeline()

    def transpile_query(
        self,
        query: str,
        source_dialect: str,
        target_dialect: str,
        include_trace: bool = False,
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
                "error_stage": None,
                "trace": None,
            }

        try:
            converted_sql, trace = self.pipeline.transpile(
                query.strip(), source_dialect, target_dialect
            )
        except TranspilationPipelineError as exc:
            return {
                "success": False,
                "converted_sql": None,
                "error_message": f"Unable to convert this SQL: {exc}",
                "error_category": "conversion",
                "error_stage": exc.stage,
                "trace": None,
            }
        except (ParseError, UnsupportedError, SqlglotError, ValueError) as exc:
            return {
                "success": False,
                "converted_sql": None,
                "error_message": f"Unable to convert this SQL: {exc}",
                "error_category": "conversion",
                "error_stage": None,
                "trace": None,
            }
        except Exception:
            return {
                "success": False,
                "converted_sql": None,
                "error_message": "An unexpected error occurred while converting the SQL.",
                "error_category": "internal",
                "error_stage": None,
                "trace": None,
            }

        return {
            "success": True,
            "converted_sql": converted_sql,
            "error_message": None,
            "error_category": None,
            "error_stage": None,
            "trace": trace.as_dict() if include_trace else None,
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
