"""Educational, staged orchestration around the vendored SQLGlot runtime.

The stages intentionally remain small and explicit. SQLGlot provides the
compiler algorithms; this module owns the pipeline contract and the data that
flows between stages.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlglot import parse
from sqlglot.errors import ErrorLevel
from sqlglot.expressions import Expression
from sqlglot.optimizer import optimize as sqlglot_optimize


PipelineStage = Literal["parse", "ast", "optimize", "generate"]


class TranspilationPipelineError(Exception):
    """An error raised by one named stage of the transpilation pipeline."""

    def __init__(self, stage: PipelineStage, message: str) -> None:
        self.stage = stage
        super().__init__(message)


@dataclass(frozen=True)
class ParsedProgram:
    """The parser output before it is accepted as the pipeline AST."""

    statements: tuple[Expression, ...]


@dataclass(frozen=True)
class AstProgram:
    """The AST contract consumed by optimization and generation."""

    statements: tuple[Expression, ...]


@dataclass(frozen=True)
class TranspilationTrace:
    """Human-readable stage snapshots used by tests and the debug API."""

    parsed_ast: tuple[str, ...]
    optimized_ast: tuple[str, ...]
    generated_sql: str

    def as_dict(self) -> dict[str, object]:
        return {
            "parsed_ast": list(self.parsed_ast),
            "optimized_ast": list(self.optimized_ast),
            "generated_sql": self.generated_sql,
        }


class TranspilationPipeline:
    """Run SQL through explicit parse, AST, optimize, and generate stages."""

    def parse(self, query: str, source_dialect: str) -> ParsedProgram:
        try:
            statements = parse(
                query,
                read=source_dialect,
                error_level=ErrorLevel.RAISE,
            )
            return ParsedProgram(tuple(statements))
        except Exception as exc:
            raise TranspilationPipelineError("parse", str(exc)) from exc

    def build_ast(self, parsed: ParsedProgram) -> AstProgram:
        try:
            if not parsed.statements or not all(
                isinstance(statement, Expression) for statement in parsed.statements
            ):
                raise ValueError("The parser did not produce SQL expression nodes.")
            return AstProgram(parsed.statements)
        except Exception as exc:
            raise TranspilationPipelineError("ast", str(exc)) from exc

    def optimize(self, ast: AstProgram, target_dialect: str) -> AstProgram:
        try:
            # Calling SQLGlot's optimizer with no rules gives us a stable,
            # explicit optimization boundary without changing the existing
            # converter's output. Future lessons can add one rule at a time.
            optimized = tuple(
                sqlglot_optimize(
                    statement,
                    dialect=target_dialect,
                    rules=(),
                )
                for statement in ast.statements
            )
            return AstProgram(optimized)
        except Exception as exc:
            raise TranspilationPipelineError("optimize", str(exc)) from exc

    def generate(self, ast: AstProgram, target_dialect: str) -> str:
        try:
            return "\n\n".join(
                statement.sql(dialect=target_dialect, pretty=True)
                for statement in ast.statements
            )
        except Exception as exc:
            raise TranspilationPipelineError("generate", str(exc)) from exc

    def transpile(
        self,
        query: str,
        source_dialect: str,
        target_dialect: str,
    ) -> tuple[str, TranspilationTrace]:
        parsed = self.parse(query, source_dialect)
        ast = self.build_ast(parsed)
        optimized = self.optimize(ast, target_dialect)
        generated_sql = self.generate(optimized, target_dialect)

        return generated_sql, TranspilationTrace(
            parsed_ast=tuple(repr(statement) for statement in ast.statements),
            optimized_ast=tuple(
                repr(statement) for statement in optimized.statements
            ),
            generated_sql=generated_sql,
        )
