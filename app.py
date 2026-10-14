from __future__ import annotations

from flask import Flask, jsonify, render_template, request
from sqlglot import transpile
from sqlglot.errors import ErrorLevel, SqlglotError


app = Flask(__name__)

DIALECTS = {
    "oracle": "Oracle",
    "mysql": "MySQL",
    "postgres": "PostgreSQL",
}


def convert_sql(source_sql: str, source_dialect: str, target_dialect: str) -> str:
    if not isinstance(source_sql, str):
        raise ValueError("source_sql must be a string.")
    if not isinstance(source_dialect, str) or not isinstance(target_dialect, str):
        raise ValueError("Source and target dialects must be strings.")

    source_sql = source_sql.strip()
    if not source_sql:
        raise ValueError("Enter a SQL query to convert.")
    if source_dialect not in DIALECTS or target_dialect not in DIALECTS:
        raise ValueError("Choose a supported source and target dialect.")

    return "\n\n".join(
        transpile(
            source_sql,
            read=source_dialect,
            write=target_dialect,
            error_level=ErrorLevel.RAISE,
            pretty=True,
        )
    )


@app.route("/", methods=["GET", "POST"])
def index():
    source_sql = ""
    source_dialect = "oracle"
    target_dialect = "mysql"
    converted_sql = ""
    error = ""

    if request.method == "POST":
        source_sql = request.form.get("source_sql", "").strip()
        source_dialect = request.form.get("source_dialect", source_dialect)
        target_dialect = request.form.get("target_dialect", target_dialect)

        try:
            converted_sql = convert_sql(source_sql, source_dialect, target_dialect)
        except ValueError as exc:
            error = str(exc)
        except SqlglotError as exc:
            error = f"Unable to convert this SQL: {exc}"

    return render_template(
        "index.html",
        dialects=DIALECTS,
        source_sql=source_sql,
        source_dialect=source_dialect,
        target_dialect=target_dialect,
        converted_sql=converted_sql,
        error=error,
    )


@app.post("/api/convert")
def api_convert():
    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify(error="Request body must be a JSON object."), 400

    try:
        converted_sql = convert_sql(
            payload.get("source_sql"),
            payload.get("source_dialect"),
            payload.get("target_dialect"),
        )
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except SqlglotError as exc:
        return jsonify(error=f"Unable to convert this SQL: {exc}"), 422

    return jsonify(
        converted_sql=converted_sql,
        source_dialect=payload["source_dialect"],
        target_dialect=payload["target_dialect"],
    )


if __name__ == "__main__":
    app.run(debug=True)
