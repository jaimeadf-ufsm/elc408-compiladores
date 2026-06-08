#!/bin/bash
set -uo pipefail

shopt -s globstar nullglob

SRC_DIR="jass"
OUT_DIR="yaml"
ok=0 fail=0

for src in "$SRC_DIR"/**/*.jass; do
    rel="${src#"$SRC_DIR"/}"
    out="$OUT_DIR/${rel%.jass}.yaml"
    
    mkdir -p "${out%/*}"

    if err=$(uv run jass "$src" -o "$out" 2>&1 >/dev/null); then
        echo "OK    $rel"
        ((ok++))
    else
        echo "FAIL  $rel" >&2
        sed 's/^/        /' <<< "$err" >&2
        ((fail++))
    fi
done

echo "----------------------------------------"
echo "Concluído: ${ok} gerado(s), ${fail} com erro."