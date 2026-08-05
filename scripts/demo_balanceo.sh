#!/usr/bin/env bash
# Demuestra el balanceo de carga mostrando qué pod atiende cada petición.
#
# Uso: ./scripts/demo_balanceo.sh [URL] [N_PETICIONES]
#   ./scripts/demo_balanceo.sh http://localhost:30080 10
set -euo pipefail

URL="${1:-http://localhost:30080}"
N="${2:-10}"

CLIENTE='{"tenure":12,"MonthlyCharges":70.35,"TotalCharges":844.20,
"gender":"Female","SeniorCitizen":"0","Partner":"Yes","Dependents":"No",
"PhoneService":"Yes","MultipleLines":"No","InternetService":"Fiber optic",
"OnlineSecurity":"No","OnlineBackup":"Yes","DeviceProtection":"No",
"TechSupport":"No","StreamingTV":"Yes","StreamingMovies":"No",
"Contract":"Month-to-month","PaperlessBilling":"Yes",
"PaymentMethod":"Electronic check"}'

echo "Enviando $N peticiones a $URL/predict"
echo

for _ in $(seq 1 "$N"); do
  curl -s -X POST "$URL/predict" \
    -H 'Content-Type: application/json' \
    -d "$CLIENTE" \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); print("  {}  p={}  modelo v{}".format(d["served_by"], d["probability"], d["model_version"]))'
done

echo
echo "Reparto por pod:"
for _ in $(seq 1 "$N"); do
  curl -s -X POST "$URL/predict" -H 'Content-Type: application/json' -d "$CLIENTE" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["served_by"])'
done | sort | uniq -c
