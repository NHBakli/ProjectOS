#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

export ANSIBLE_CONFIG="$repo_root/infrastructure/ansible.cfg"
export ANSIBLE_LOCAL_TEMP="${TMPDIR:-/tmp}/projectos-ansible-local"
export ANSIBLE_REMOTE_TEMP="${TMPDIR:-/tmp}/projectos-ansible-remote"
export XDG_CACHE_HOME="${TMPDIR:-/tmp}/projectos-cache"

yamllint -d '{extends: relaxed, rules: {line-length: {max: 120}}}' \
  .github/workflows/ci.yml infrastructure/ansible/inventories/production/hosts.example.yml \
  infrastructure/ansible/inventories/production/k3s-approval.example.yml \
  infrastructure/ansible/requirements.yml \
  infrastructure/ansible/playbooks/ infrastructure/ansible/roles/k3s/defaults/ \
  infrastructure/ansible/roles/k3s/tasks/ infrastructure/ansible/roles/k3s/handlers/ \
  infrastructure/kind/cluster.yaml kubernetes/smoke/ helm/
for playbook in infrastructure/ansible/playbooks/*.yml; do
  ansible-playbook --syntax-check "$playbook"
done
ansible-lint infrastructure/ansible/playbooks/*.yml
