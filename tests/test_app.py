import unittest

import sqlglot

from app import app
from transpilation_pipeline import TranspilationPipeline
from transpiler_wrapper import SQLTranspilationEngine


class ConverterTestCase(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def test_index_renders_supported_dialects(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Oracle", response.data)
        self.assertIn(b"MySQL", response.data)
        self.assertIn(b"PostgreSQL", response.data)

    def test_converts_oracle_to_mysql(self):
        response = self.client.post(
            "/",
            data={
                "source_sql": "SELECT NVL(name, 'unknown') FROM employees",
                "source_dialect": "oracle",
                "target_dialect": "mysql",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"COALESCE(name, &#39;unknown&#39;)", response.data)

    def test_converts_mysql_to_postgres(self):
        response = self.client.post(
            "/",
            data={
                "source_sql": "SELECT IFNULL(name, 'unknown') FROM employees",
                "source_dialect": "mysql",
                "target_dialect": "postgres",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"COALESCE(name, &#39;unknown&#39;)", response.data)

    def test_converts_postgres_to_oracle(self):
        response = self.client.post(
            "/",
            data={
                "source_sql": "SELECT CURRENT_DATE",
                "source_dialect": "postgres",
                "target_dialect": "oracle",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"CURRENT_DATE", response.data)

    def test_blank_query_shows_error(self):
        response = self.client.post("/", data={"source_sql": ""})

        self.assertIn(b"Enter a SQL query to convert.", response.data)

    def test_invalid_query_shows_error(self):
        response = self.client.post(
            "/",
            data={
                "source_sql": "SELECT * FROM (",
                "source_dialect": "mysql",
                "target_dialect": "oracle",
            },
        )

        self.assertIn(b"Unable to convert this SQL", response.data)
        self.assertIn(
            b'placeholder="Converted query will appear here."></textarea>',
            response.data,
        )

    def test_api_converts_oracle_to_mysql(self):
        response = self.client.post(
            "/api/convert",
            json={
                "source_sql": "SELECT NVL(name, 'unknown') FROM employees",
                "source_dialect": "oracle",
                "target_dialect": "mysql",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "application/json")
        self.assertEqual(response.json["source_dialect"], "oracle")
        self.assertEqual(response.json["target_dialect"], "mysql")
        self.assertIn("COALESCE(name, 'unknown')", response.json["converted_sql"])

    def test_api_converts_mysql_to_postgres(self):
        response = self.client.post(
            "/api/convert",
            json={
                "source_sql": "SELECT IFNULL(name, 'unknown') FROM employees",
                "source_dialect": "mysql",
                "target_dialect": "postgres",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("COALESCE(name, 'unknown')", response.json["converted_sql"])

    def test_api_converts_postgres_to_oracle(self):
        response = self.client.post(
            "/api/convert",
            json={
                "source_sql": "SELECT CURRENT_DATE",
                "source_dialect": "postgres",
                "target_dialect": "oracle",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("CURRENT_DATE", response.json["converted_sql"])

    def test_api_rejects_non_json_body(self):
        response = self.client.post("/api/convert", data="not json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["error"], "Request body must be a JSON object.")

    def test_api_rejects_missing_and_invalid_values(self):
        missing_sql = self.client.post(
            "/api/convert",
            json={"source_dialect": "oracle", "target_dialect": "mysql"},
        )
        invalid_dialect = self.client.post(
            "/api/convert",
            json={
                "source_sql": "SELECT 1",
                "source_dialect": "sqlite",
                "target_dialect": "mysql",
            },
        )

        self.assertEqual(missing_sql.status_code, 400)
        self.assertEqual(missing_sql.json["error"], "source_sql must be a string.")
        self.assertEqual(invalid_dialect.status_code, 400)
        self.assertEqual(
            invalid_dialect.json["error"],
            "Choose a supported source and target dialect.",
        )

    def test_api_rejects_invalid_sql(self):
        response = self.client.post(
            "/api/convert",
            json={
                "source_sql": "SELECT * FROM (",
                "source_dialect": "mysql",
                "target_dialect": "oracle",
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("Unable to convert this SQL", response.json["error"])

    def test_api_debug_returns_pipeline_trace(self):
        response = self.client.post(
            "/api/convert/debug",
            json={
                "source_sql": "SELECT NVL(name, 'unknown') FROM employees",
                "source_dialect": "oracle",
                "target_dialect": "mysql",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("parsed_ast", response.json["trace"])
        self.assertIn("optimized_ast", response.json["trace"])
        self.assertIn("COALESCE(name, 'unknown')", response.json["converted_sql"])

    def test_debug_api_rejects_invalid_sql_with_stage(self):
        response = self.client.post(
            "/api/convert/debug",
            json={
                "source_sql": "SELECT * FROM (",
                "source_dialect": "mysql",
                "target_dialect": "oracle",
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json["error_stage"], "parse")


class SQLTranspilationEngineTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = SQLTranspilationEngine()

    def test_engine_defines_supported_dialects(self):
        self.assertEqual(
            self.engine.supported_dialects,
            frozenset({"mysql", "postgres", "oracle"}),
        )

    def test_engine_returns_successful_conversion_result(self):
        result = self.engine.transpile_query(
            "SELECT NVL(name, 'unknown') FROM employees", "oracle", "mysql"
        )

        self.assertTrue(result["success"])
        self.assertIn("COALESCE(name, 'unknown')", result["converted_sql"])
        self.assertIsNone(result["error_message"])
        self.assertIsNone(result["error_category"])

    def test_engine_returns_validation_result_for_blank_query(self):
        result = self.engine.transpile_query("   ", "oracle", "mysql")

        self.assertFalse(result["success"])
        self.assertIsNone(result["converted_sql"])
        self.assertEqual(result["error_message"], "Enter a SQL query to convert.")
        self.assertEqual(result["error_category"], "validation")

    def test_engine_returns_validation_result_for_invalid_dialect(self):
        result = self.engine.transpile_query("SELECT 1", "sqlite", "mysql")

        self.assertFalse(result["success"])
        self.assertEqual(
            result["error_message"], "Choose a supported source and target dialect."
        )
        self.assertEqual(result["error_category"], "validation")

    def test_engine_returns_conversion_result_for_invalid_sql(self):
        result = self.engine.transpile_query("SELECT * FROM (", "mysql", "oracle")

        self.assertFalse(result["success"])
        self.assertIsNone(result["converted_sql"])
        self.assertIn("Unable to convert this SQL", result["error_message"])
        self.assertEqual(result["error_category"], "conversion")
        self.assertEqual(result["error_stage"], "parse")

    def test_engine_returns_trace_for_multiple_statements(self):
        result = self.engine.transpile_query(
            "SELECT 1; SELECT 2", "mysql", "postgres", include_trace=True
        )

        self.assertTrue(result["success"])
        self.assertEqual(len(result["trace"]["parsed_ast"]), 2)
        self.assertEqual(result["trace"]["parsed_ast"], result["trace"]["optimized_ast"])
        self.assertIn("SELECT\n  1", result["converted_sql"])


class TranspilationPipelineTestCase(unittest.TestCase):
    def test_pipeline_exposes_each_stage(self):
        pipeline = TranspilationPipeline()
        parsed = pipeline.parse("SELECT 1", "mysql")
        ast = pipeline.build_ast(parsed)
        optimized = pipeline.optimize(ast, "postgres")
        generated = pipeline.generate(optimized, "postgres")

        self.assertEqual(len(parsed.statements), 1)
        self.assertEqual(ast.statements, parsed.statements)
        self.assertEqual(optimized.statements[0].sql(), "SELECT 1")
        self.assertEqual(generated, "SELECT\n  1")

    def test_application_uses_vendored_sqlglot(self):
        self.assertTrue(sqlglot.__file__.startswith(app.root_path))
        self.assertEqual(sqlglot.__version__, "26.3.0")


if __name__ == "__main__":
    unittest.main()
