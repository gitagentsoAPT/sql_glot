import unittest

from app import app


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


if __name__ == "__main__":
    unittest.main()
