#!/usr/bin/env python3
"""Envoie un faux événement Plane signé comme Plane v1.4.2 (webhook_task.py)."""
import hashlib
import hmac
import json
import sys
import urllib.request

URL = "http://127.0.0.1:5679/webhook/f91278c2-9a48-4717-be97-0450f85248be"
PROJET = "ID-DU-PROJET-PLANE"


def lab(*noms):
    return [{"id": f"l-{n}", "name": n, "color": "#000"} for n in noms]


def payload(action, labels, projet=PROJET, champ=None, issue="11111111-aaaa-bbbb-cccc-000000000001",
            nom="Écran de connexion « mobile » \"v2\""):
    return {
        "event": "issue", "action": action, "webhook_id": "w", "workspace_id": "ws",
        "workspace_slug": "flowly",
        "data": {"id": issue, "name": nom, "project": projet,
                 "description_stripped": "Ligne 1\nÀ faire : l'API", "labels": labels, "sequence_id": 8},
        "activity": {"field": champ, "new_value": None, "old_value": None, "actor": {"id": "u"}},
    }


CAS = {
    "creation": payload("created", lab("Frontend ", "backend", "bug")),
    "rejeu": payload("created", lab("Frontend ", "backend", "bug")),
    "ajout_mobile": payload("updated", lab("frontend", "backend", "mobile"), champ="label_ids"),
    "autre_projet": payload("created", lab("devops"), projet="autre"),
    "champ_nom": payload("updated", lab("devops"), champ="name", issue="22222222-aaaa-bbbb-cccc-000000000002"),
    "sans_label_equipe": payload("created", lab("bug"), issue="33333333-aaaa-bbbb-cccc-000000000003"),
    "deepl_en_panne": payload("created", lab("DevOps"), issue="44444444-aaaa-bbbb-cccc-000000000004",
                              nom="PANNE de traduction"),
}

cas = sys.argv[1]
secret = sys.argv[2] if len(sys.argv) > 2 else "secret-test"
p = CAS[cas]
corps = json.dumps(p).encode("utf-8")  # comme requests(json=payload)
sig = hmac.new(secret.encode(), json.dumps(p).encode("utf-8"), hashlib.sha256).hexdigest()
req = urllib.request.Request(URL, data=corps, method="POST", headers={
    "Content-Type": "application/json", "User-Agent": "Autopilot",
    "X-Plane-Event": "issue", "X-Plane-Signature": sig})
with urllib.request.urlopen(req, timeout=10) as r:
    print(cas, "->", r.status)
