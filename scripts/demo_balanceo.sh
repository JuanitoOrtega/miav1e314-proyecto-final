#!/usr/bin/env bash
# Demuestra el balanceo de carga mostrando qué pod atiende cada petición.
#
# Cada pod recibe su nombre en la variable POD_NAME mediante la Downward API
# de Kubernetes y lo devuelve en el campo served_by de cada respuesta.
#
#   ./scripts/demo_balanceo.sh                              # local, 10 peticiones
#   ./scripts/demo_balanceo.sh https://churn.juanitodev.com 20
set -euo pipefail

URL="${1:-http://localhost:30080}"
N="${2:-10}"

CLIENTE='{
  "tenure": 12, "MonthlyCharges": 70.35, "TotalCharges": 844.20,
  "gender": "Female", "SeniorCitizen": "0", "Partner": "Yes",
  "Dependents": "No", "PhoneService": "Yes", "MultipleLines": "No",
  "InternetService": "Fiber optic", "OnlineSecurity": "No",
  "OnlineBackup": "Yes", "DeviceProtection": "No", "TechSupport": "No",
  "StreamingTV": "Yes", "StreamingMovies": "No",
  "Contract": "Month-to-month", "PaperlessBilling": "Yes",
  "PaymentMethod": "Electronic check"
}'

extraer() {
  python3 -c 'import sys,json; d=json.load(sys.stdin); print(d["served_by"], d["probability"])'
}

echo "Enviando $N peticiones a $URL/predict"
echo

TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT

for i in $(seq 1 "$N"); do
  respuesta=$(curl -s -X POST "$URL/predict" \
                -H 'Content-Type: application/json' \
                -d "$CLIENTE" | extraer)
  pod=${respuesta%% *}
  prob=${respuesta##* }
  printf "  %2d  %-32s p=%s\n" "$i" "$pod" "$prob"
  echo "$pod" >> "$TMP"
done

echo
echo "Reparto entre pods:"
sort "$TMP" | uniq -c | awk '{printf "  %3d peticiones  %s\n", $1, $2}'

distintos=$(sort -u "$TMP" | wc -l | tr -d ' ')
echo
if [ "$distintos" -ge 2 ]; then
  echo "BALANCEO DEMOSTRADO: $distintos pods distintos atendieron las peticiones."
else
  echo "ATENCION: todas las peticiones las atendio el mismo pod."
  echo "Comprueba que hay mas de una replica en Ready:  kubectl get pods"
  exit 1
fi
