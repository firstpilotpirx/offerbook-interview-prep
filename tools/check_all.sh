#!/usr/bin/env bash
# Runs all checks and builds on the sample. Run after any change to templates, schemas or scripts.
#   bash tools/check_all.sh [prep folder, default examples/sample]
set -euo pipefail
cd "$(dirname "$0")/.."
DIR="${1:-examples/sample}"
OUT="$(mktemp -d)"
# Python with the pinned dependencies: the plugin's own environment (created on first run)
if python3 -c "import yaml, jsonschema" 2>/dev/null; then PY=python3; else
  PY="$(bash tools/run --check | tail -1 | sed 's/^ok: //')/bin/python"
fi
step(){ printf '\n── %s\n' "$1"; }
step "plugin rules"; "$PY" tools/check_rules.py
step "profiles";            "$PY" tools/validate_profiles.py
step "materials and deck"; "$PY" tools/validate_content.py --dir "$DIR" --require-en
step "vocabulary candidates"; "$PY" tools/rank_words.py "$DIR/content" --weight stories=3 --weight answers=3 --out "$OUT/candidates.yaml"
step "interviews report";     "$PY" tools/interviews_report.py --dir "$DIR" > "$OUT/report.md" && head -5 "$OUT/report.md"
step "stage questions"; "$PY" tools/stage_question.py --profile backend --level senior > "$OUT/stages.json" && "$PY" -c "import json;d=json.load(open('$OUT/stages.json'));print(len(d['questions']),'questions,',sum(len(q['options']) for q in d['questions']),'stages')"
step "fundamentals questions"; mkdir -p "$OUT/th/prep" && printf "answers:\n  level: senior\n  databases: [postgresql, redis]\n  messaging: [kafka]\n" > "$OUT/th/prep/answers.yaml" && "$PY" tools/theory_question.py --profile backend --dir "$OUT/th" > "$OUT/theory.json" && "$PY" -c "import json;d=json.load(open('$OUT/theory.json'));print(len(d['all']),'blocks,',len(d['recommended']),'recommended')"
step "material depth"; "$PY" tools/depth.py --dir "$DIR" | tail -1 || true
step "update on a copy"; cp -r "$DIR" "$OUT/up" && rm -f "$OUT/up/prep/session.yaml" && sed -i.bak '/explain-language/d' "$OUT/up/prep/answers.yaml" \
  && printf '{"done":{"x.y":true},"skip":{},"collapsed":{},"expanded":{}}' > "$OUT/up/prep/page-state.json" \
  && "$PY" tools/migrate.py --dir "$OUT/up" > "$OUT/m1.txt" && head -1 "$OUT/m1.txt" \
  && "$PY" tools/migrate.py --dir "$OUT/up" > "$OUT/m2.txt" && head -1 "$OUT/m2.txt" \
  && "$PY" tools/backup.py --dir "$OUT/up" list > "$OUT/b.txt" && head -1 "$OUT/b.txt" \
  && "$PY" tools/whats_new.py --dir "$DIR" --from 0.8.0 > "$OUT/w.txt" && head -2 "$OUT/w.txt"
step "hub menu";         "$PY" tools/next_steps.py --dir "$DIR"
step "page on an empty folder"; mkdir -p "$OUT/empty" && "$PY" tools/build_page.py --dir "$OUT/empty" --out "$OUT/empty.html"
step "page";           "$PY" tools/build_page.py --dir "$DIR" --out "$OUT/index.html"
for cv in "$DIR"/prep/cv/*.yaml; do
  [ -e "$cv" ] || continue
  step "resume $(basename "$cv")"
  "$PY" tools/cv_lint.py "$cv" || true
  "$PY" tools/build_cv.py "$cv" --out "$OUT/$(basename "${cv%.yaml}").html" --md
done
printf '\nDone. Results: %s\n' "$OUT"
