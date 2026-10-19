"""Educational, staged orchestration around the vendored SQLGlot runtime.

The stages intentionally remain small and explicit. SQLGlot provides the
compiler algorithms; this module owns the pipeline contract and the data that
flows between stages.
"""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Literal
from uuid import uuid4

from sqlglot import parse
from sqlglot import expressions as exp
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
class RuleDefinition:
    """Metadata and implementation for one student-owned optimization rule."""

    name: str
    pass_number: int
    description: str
    apply: object


@dataclass(frozen=True)
class RuleApplication:
    """One rule that changed an AST program."""

    rule_name: str
    input_stage_number: int
    output_stage_number: int
    step_number: int
    ast_delta: dict[str, object]
    exec_time_us: int


@dataclass(frozen=True)
class ParsedProgram:
    """The parser output before it is accepted as the pipeline AST."""

    statements: tuple[Expression, ...]


@dataclass(frozen=True)
class AstProgram:
    """The AST contract consumed by optimization and generation."""

    statements: tuple[Expression, ...]


@dataclass(frozen=True)
class AstSnapshot:
    """A serializable AST state captured during one conversion."""

    stage: str
    stage_number: int
    ast_json: tuple[dict[str, object], ...]
    node_count: int
    generated_sql: str | None = None


@dataclass(frozen=True)
class TranspilationTrace:
    """Human-readable stage snapshots used by tests and the debug API."""

    request_id: str
    raw_sql: str
    source_dialect: str
    target_dialect: str
    parsed_ast: tuple[str, ...]
    optimized_ast: tuple[str, ...]
    generated_sql: str
    snapshots: tuple[AstSnapshot, ...]
    transformations: tuple[RuleApplication, ...]

    @staticmethod
    def rule_definitions() -> tuple[RuleDefinition, ...]:
        return RULE_DEFINITIONS

    def as_dict(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "source_dialect": self.source_dialect,
            "target_dialect": self.target_dialect,
            "parsed_ast": list(self.parsed_ast),
            "optimized_ast": list(self.optimized_ast),
            "generated_sql": self.generated_sql,
            "snapshots": [
                {
                    "stage": snapshot.stage,
                    "stage_number": snapshot.stage_number,
                    "ast_json": list(snapshot.ast_json),
                    "node_count": snapshot.node_count,
                    "generated_sql": snapshot.generated_sql,
                }
                for snapshot in self.snapshots
            ],
            "transformations": [
                {
                    "rule_name": transformation.rule_name,
                    "input_stage_number": transformation.input_stage_number,
                    "output_stage_number": transformation.output_stage_number,
                    "step_number": transformation.step_number,
                    "ast_delta": transformation.ast_delta,
                    "exec_time_us": transformation.exec_time_us,
                }
                for transformation in self.transformations
            ],
        }


def _program_dump(program: AstProgram) -> tuple[dict[str, object], ...]:
    return tuple(statement.dump() for statement in program.statements)


def _node_count(program: AstProgram) -> int:
    return sum(1 for statement in program.statements for _ in statement.walk())


def _replace_numeric_comparisons(expression: Expression) -> Expression:
    if not isinstance(expression, exp.EQ):
        return expression
    left = expression.this
    right = expression.expression
    if not isinstance(left, exp.Literal) or not isinstance(right, exp.Literal):
        return expression
    if left.is_string or right.is_string or not left.is_number or not right.is_number:
        return expression
    return exp.Boolean(this=left.to_py() == right.to_py())


def _remove_boolean_identities(expression: Expression) -> Expression:
    if not isinstance(expression, (exp.And, exp.Or)):
        return expression
    left = expression.this
    right = expression.expression
    if isinstance(right, exp.Boolean):
        if isinstance(expression, exp.And) and right.this:
            return left
        if isinstance(expression, exp.Or) and not right.this:
            return left
    if isinstance(left, exp.Boolean):
        if isinstance(expression, exp.And) and left.this:
            return right
        if isinstance(expression, exp.Or) and not left.this:
            return right
    return expression


RULE_DEFINITIONS = (
    RuleDefinition(
        name="constant_comparison_folding",
        pass_number=1,
        description="Folds equality comparisons between numeric literals.",
        apply=_replace_numeric_comparisons,
    ),
    RuleDefinition(
        name="boolean_identity_simplification",
        pass_number=2,
        description="Removes AND TRUE and OR FALSE identity predicates.",
        apply=_remove_boolean_identities,
    ),
)


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
            return AstProgram(
                tuple(
                    sqlglot_optimize(
                        statement,
                        dialect=target_dialect,
                        rules=(),
                    )
                    for statement in ast.statements
                )
            )
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
        snapshots = [
            AstSnapshot(
                stage="initial",
                stage_number=0,
                ast_json=_program_dump(optimized),
                node_count=_node_count(optimized),
            )
        ]
        transformations: list[RuleApplication] = []
        current = optimized
        for definition in RULE_DEFINITIONS:
            started = time.perf_counter_ns()
            next_program = AstProgram(
                tuple(
                    statement.transform(definition.apply, copy=True)
                    for statement in current.statements
                )
            )
            elapsed_us = max(1, (time.perf_counter_ns() - started) // 1_000)
            before_dump = _program_dump(current)
            after_dump = _program_dump(next_program)
            if before_dump == after_dump:
                continue
            output_stage_number = len(snapshots)
            snapshots.append(
                AstSnapshot(
                    stage="after_rule",
                    stage_number=output_stage_number,
                    ast_json=after_dump,
                    node_count=_node_count(next_program),
                )
            )
            transformations.append(
                RuleApplication(
                    rule_name=definition.name,
                    input_stage_number=output_stage_number - 1,
                    output_stage_number=output_stage_number,
                    step_number=len(transformations) + 1,
                    ast_delta={"before": before_dump, "after": after_dump},
                    exec_time_us=elapsed_us,
                )
            )
            current = next_program

        generated_sql = self.generate(current, target_dialect)
        snapshots.append(
            AstSnapshot(
                stage="final",
                stage_number=len(snapshots),
                ast_json=_program_dump(current),
                node_count=_node_count(current),
                generated_sql=generated_sql,
            )
        )

        return generated_sql, TranspilationTrace(
            request_id=str(uuid4()),
            raw_sql=query,
            source_dialect=source_dialect,
            target_dialect=target_dialect,
            parsed_ast=tuple(repr(statement) for statement in ast.statements),
            optimized_ast=tuple(repr(statement) for statement in current.statements),
            generated_sql=generated_sql,
            snapshots=tuple(snapshots),
            transformations=tuple(transformations),
        )
