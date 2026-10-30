#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

helm_bin="${HELM_BIN:-helm}"
chart_dir="${PROJECTOS_CHART_CACHE:-${TMPDIR:-/tmp}/projectos-chart-cache}"
mkdir -p "$chart_dir"

if [[ -n "${PROJECTOS_N8N_CHART_ARCHIVE:-}" ]]; then
  n8n_chart="$PROJECTOS_N8N_CHART_ARCHIVE"
else
  "$helm_bin" pull oci://ghcr.io/n8n-io/n8n-helm-chart/n8n \
    --version 1.17.0 --destination "$chart_dir"
  n8n_chart="$chart_dir/n8n-1.17.0.tgz"
fi

if [[ -n "${PROJECTOS_PLANE_CE_CHART_ARCHIVE:-}" ]]; then
  plane_ce_chart="$PROJECTOS_PLANE_CE_CHART_ARCHIVE"
else
  plane_ce_chart="$chart_dir/plane-ce-1.8.5.tgz"
  curl --fail --silent --show-error --location \
    --output "$plane_ce_chart" \
    https://github.com/makeplane/helm-charts/releases/download/plane-ce-1.8.5/plane-ce-1.8.5.tgz
fi

if [[ -n "${PROJECTOS_PLANE_COMMERCIAL_CHART_ARCHIVE:-}" ]]; then
  plane_commercial_chart="$PROJECTOS_PLANE_COMMERCIAL_CHART_ARCHIVE"
else
  plane_commercial_chart="$chart_dir/plane-enterprise-3.10.12.tgz"
  curl --fail --silent --show-error --location \
    --output "$plane_commercial_chart" \
    https://github.com/makeplane/helm-charts/releases/download/plane-enterprise-3.10.12/plane-enterprise-3.10.12.tgz
fi

printf '%s\n' \
  "15a83b48bb53ab052e60d6ef553bb787912c234b2439101ef9dc574afcad1717  $n8n_chart" \
  "9d68ae1eb2d9e1a6181d1779063fa7feb949fcd48de31b2df4d847ea1eece755  $plane_ce_chart" \
  "e75e9a5dfa0a3f8100614916bb130b8d4bdc7021177f6ef47a25853fdb4bc621  $plane_commercial_chart" \
  | sha256sum --check --status

"$helm_bin" lint "$n8n_chart" -f helm/n8n-values.example.yaml
"$helm_bin" lint "$plane_ce_chart" -f helm/plane-ce-values.yaml
"$helm_bin" lint "$plane_commercial_chart" -f helm/plane-commercial-values.example.yaml

n8n_render="$chart_dir/n8n-rendered.yaml"
plane_ce_render="$chart_dir/plane-ce-rendered.yaml"
plane_commercial_render="$chart_dir/plane-commercial-rendered.yaml"
"$helm_bin" template n8n "$n8n_chart" -n n8n \
  -f helm/n8n-values.example.yaml > "$n8n_render"
"$helm_bin" template plane-app "$plane_ce_chart" -n plane \
  -f helm/plane-ce-values.yaml > "$plane_ce_render"
"$helm_bin" template plane-app "$plane_commercial_chart" -n plane \
  -f helm/plane-commercial-values.example.yaml > "$plane_commercial_render"

python3 - "$n8n_render" "$plane_ce_render" "$plane_commercial_render" <<'PY'
import sys
from collections import Counter
from pathlib import Path

import yaml

def read_objects(path):
    return [obj for obj in yaml.safe_load_all(Path(path).read_text()) if isinstance(obj, dict)]


objects = read_objects(sys.argv[1])
kinds = Counter(obj.get('kind') for obj in objects)
config = next(obj for obj in objects if obj.get('kind') == 'ConfigMap')
assert kinds['Secret'] == 0, 'Le chart a généré un Secret inattendu'
assert kinds['PersistentVolumeClaim'] == 1, 'Un PVC n8n est attendu'
assert kinds['Ingress'] == 1, 'Un Ingress n8n est attendu'
assert kinds['Deployment'] == 1, 'Un seul Deployment n8n est attendu'
assert config['data']['DB_TYPE'] == 'sqlite', 'Le mode SQLite est attendu'
print('Rendu n8n vérifié : SQLite, PVC, Ingress, aucun Secret généré')

for edition, path, stateful_sets in (
    ('Plane CE', sys.argv[2], 4),
    ('Plane Commercial Free', sys.argv[3], 5),
):
    objects = read_objects(path)
    kinds = Counter(obj.get('kind') for obj in objects)
    routes = [obj for obj in objects if obj.get('kind') == 'IngressRoute']
    assert kinds['Secret'] == 0, f'{edition} a généré un Secret inattendu'
    assert kinds['StatefulSet'] == stateful_sets, f'{edition} : StatefulSets inattendus'
    assert len(routes) == 1, f'{edition} : un IngressRoute est attendu'
    assert routes[0]['spec']['tls']['secretName'] == 'plane-tls', f'{edition} : TLS non référencé'
    print(f'{edition} vérifié : aucun Secret généré, IngressRoute TLS, {stateful_sets} StatefulSets')
PY
