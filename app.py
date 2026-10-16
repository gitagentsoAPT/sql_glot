from __future__ import annotations

from flask import Flask, jsonify, render_template, request

from transpiler_wrapper import SQLTranspilationEngine


app = Flask(__name__)

DIALECTS = {
    "oracle": "Oracle",
    "mysql": "MySQL",
    "postgres": "PostgreSQL",
}

transpilation_engine = SQLTranspilationEngine()


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

        result = transpilation_engine.transpile_query(
            source_sql, source_dialect, target_dialect
        )
        if result["success"]:
            converted_sql = result["converted_sql"] or ""
        else:
            error = result["error_message"] or "Unable to convert this SQL."

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

    result = transpilation_engine.transpile_query(
        payload.get("source_sql"),
        payload.get("source_dialect"),
        payload.get("target_dialect"),
    )

    if not result["success"]:
        status_code = 400 if result["error_category"] == "validation" else 422
        return jsonify(error=result["error_message"]), status_code

    return jsonify(
        converted_sql=result["converted_sql"],
        source_dialect=payload["source_dialect"],
        target_dialect=payload["target_dialect"],
    )


if __name__ == "__main__":
    app.run(debug=True)
