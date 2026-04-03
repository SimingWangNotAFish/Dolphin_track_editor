from flask import Flask, render_template, request, jsonify, send_file
import pandas as pd
import io

app = Flask(__name__)

CANONICAL_COLUMNS = {
    "frame_number": ["frame_number", "frame", "Frame", "frame_num"],
    "X": ["X", "x", "x_coord", "x_coordinate"],
    "Y": ["Y", "y", "y_coord", "y_coordinate"],
    "global_id": ["global_id", "id", "ID", "track_id", "name"],
}


def resolve_columns(df):
    resolved = {}
    for canonical, aliases in CANONICAL_COLUMNS.items():
        for alias in aliases:
            if alias in df.columns:
                resolved[canonical] = alias
                break
    missing = [key for key in CANONICAL_COLUMNS if key not in resolved]
    return resolved, missing

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/parse_csv", methods=["POST"])
def parse_csv():
    """Parse uploaded CSV and return all data to browser. That's all the server does."""
    file = request.files.get("csv_file")
    if not file:
        return jsonify({"error": "No file provided"}), 400
    try:
        df = pd.read_csv(file, sep=None, engine="python")
        df.columns = [c.strip() for c in df.columns]
        resolved, missing = resolve_columns(df)
        if missing:
            return jsonify({"error": f"Missing columns: {missing}"}), 400

        # Pass through all columns while also exposing a consistent set of keys
        records = []
        for _, row in df.iterrows():
            rec = {}
            for col in df.columns:
                value = row[col]
                rec[col] = None if pd.isna(value) else value

            rec["frame_number"] = int(row[resolved["frame_number"]])
            rec["X"] = float(row[resolved["X"]])
            rec["Y"] = float(row[resolved["Y"]])
            rec["global_id"] = str(row[resolved["global_id"]])

            if "type" not in rec:
                rec["type"] = ""
            if "is_imputed" not in rec or pd.isna(rec["is_imputed"]):
                rec["is_imputed"] = 0
            else:
                try:
                    rec["is_imputed"] = int(rec["is_imputed"])
                except (TypeError, ValueError):
                    rec["is_imputed"] = str(rec["is_imputed"])
            if "correction_flag" not in rec or pd.isna(rec["correction_flag"]):
                rec["correction_flag"] = "none"
            else:
                rec["correction_flag"] = str(rec["correction_flag"])

            records.append(rec)

        return jsonify({
            "success": True,
            "n_rows": len(records),
            "data": records,
            "column_order": list(df.columns),
            "resolved_columns": resolved,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/export_csv", methods=["POST"])
def export_csv():
    """Receive corrected data from browser, write CSV, send back."""
    body = request.json
    records = body.get("data", [])
    column_order = body.get("column_order", [])
    resolved_columns = body.get("resolved_columns", {})
    if not records:
        return jsonify({"error": "No data"}), 400

    export_rows = []
    for record in records:
        row = {
            k: v for k, v in record.items()
            if not str(k).startswith("__")
            and (k in column_order or k not in CANONICAL_COLUMNS)
        }
        frame_col = resolved_columns.get("frame_number", "frame_number")
        x_col = resolved_columns.get("X", "X")
        y_col = resolved_columns.get("Y", "Y")
        id_col = resolved_columns.get("global_id", "global_id")

        row[frame_col] = record.get("frame_number")
        row[x_col] = record.get("X")
        row[y_col] = record.get("Y")
        row[id_col] = record.get("global_id")
        export_rows.append(row)

    df = pd.DataFrame(export_rows)
    if column_order:
        ordered = [c for c in column_order if c in df.columns]
        extras = [c for c in df.columns if c not in ordered]
        df = df[ordered + extras]

    sort_frame = resolved_columns.get("frame_number", "frame_number")
    sort_id = resolved_columns.get("global_id", "global_id")
    if sort_frame in df.columns and sort_id in df.columns:
        df = df.sort_values([sort_frame, sort_id]).reset_index(drop=True)

    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return send_file(
        io.BytesIO(buf.getvalue().encode()),
        mimetype="text/csv",
        as_attachment=True,
        download_name="corrected_tracks.csv"
    )

if __name__ == "__main__":
    print("\n" + "="*50)
    print("  Dolphin Track Editor  [fast client-side build]")
    print("  Open your browser and go to:")
    print("  http://127.0.0.1:5000")
    print("="*50 + "\n")
    app.run(debug=False, port=5000)
