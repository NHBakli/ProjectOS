#!/usr/bin/env bash
# Teste n8n/workflows/plane-vers-github.json dans un n8n local (Docker),
# face à de fausses API Plane, GitHub et DeepL. Ne touche ni au VPS ni à GitHub.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

image="docker.n8n.io/n8nio/n8n:2.44.5"
nom="projectos-n8n-test"
travail="$(mktemp -d)"
port_mock=8099

nettoyer() {
  docker rm -f "$nom" >/dev/null 2>&1 || true
  [[ -n "${pid_mock:-}" ]] && kill "$pid_mock" 2>/dev/null || true
  rm -rf "$travail"
}
trap nettoyer EXIT

passerelle="$(docker network inspect bridge -f '{{(index .IPAM.Config 0).Gateway}}')"
api="http://${passerelle}:${port_mock}"

# Copie de test : fausses API, secret de test, pas d'identifiants.
python3 - "$travail/wf.json" "$api" <<'EOF'
import json, sys
sortie, api = sys.argv[1], sys.argv[2]
s = open("n8n/workflows/plane-vers-github.json", encoding="utf-8").read()
s = s.replace("http://plane-app-api.plane.svc.cluster.local:8000", api)
s = s.replace("https://api.github.com", api + "/github")
s = s.replace("https://api-free.deepl.com", api + "/deepl")
s = s.replace("COLLER_ICI_LE_SECRET_DU_WEBHOOK_PLANE", "secret-test")
w = json.loads(s)
w["id"] = "testPlaneGithub1"
for n in w["nodes"]:
    if n["type"] == "n8n-nodes-base.httpRequest":
        n["parameters"]["authentication"] = "none"
        n["parameters"].pop("genericAuthType", None)
json.dump([w], open(sortie, "w", encoding="utf-8"), ensure_ascii=False)
EOF
chmod 644 "$travail/wf.json"

python3 n8n/tests/faux-plane-github.py "$travail/appels.log" "$passerelle" &
pid_mock=$!
touch "$travail/appels.log"

docker run -d --name "$nom" -p 127.0.0.1:5679:5678 -e N8N_DIAGNOSTICS_ENABLED=false \
  -v "$travail/wf.json:/tmp/wf.json:ro" "$image" >/dev/null
attendre() {
  for _ in $(seq 60); do
    curl -fs http://127.0.0.1:5679/healthz >/dev/null 2>&1 && return 0
    sleep 2
  done
  echo "n8n ne démarre pas" >&2
  exit 1
}
attendre
docker exec "$nom" n8n import:workflow --input=/tmp/wf.json >/dev/null 2>&1
docker exec "$nom" n8n publish:workflow --id=testPlaneGithub1 >/dev/null 2>&1
docker restart "$nom" >/dev/null
attendre
sleep 5

echecs=0
verifier() { # cas, secret, issues attendues, texte attendu dans les issues créées (facultatif)
  local avant apres creees
  avant=$(wc -l <"$travail/appels.log")
  python3 n8n/tests/envoyer-evenement-plane.py "$1" "$2" >/dev/null
  sleep 5
  apres=$(tail -n +$((avant + 1)) "$travail/appels.log")
  creees=$(grep -c '"p": "/github/repos/' <<<"$apres" || true)
  if [[ "$creees" == "$3" ]] && { [[ -z "${4:-}" ]] || grep '"p": "/github/repos/' <<<"$apres" | grep -qF -- "$4"; }; then
    echo "OK    $1 ($2) : $creees issue(s) créée(s)"
  else
    echo "ÉCHEC $1 ($2) : $creees issue(s) créée(s), attendu $3 ${4:+avec « $4 »}"
    echecs=$((echecs + 1))
  fi
}

verifier creation secret-test 2 '"title": "EN: Écran'   # frontend + backend, titre traduit
verifier rejeu secret-test 0             # liens déjà présents
verifier ajout_mobile secret-test 1      # seul mobile est nouveau
verifier autre_projet secret-test 0
verifier champ_nom secret-test 0
verifier sans_label_equipe secret-test 0
verifier creation mauvais-secret 0       # signature refusée
verifier deepl_en_panne secret-test 1 'Translation unavailable'   # DeepL en panne : issue en français

echo "Résultat : $echecs échec(s)"
[[ "$echecs" == 0 ]]
