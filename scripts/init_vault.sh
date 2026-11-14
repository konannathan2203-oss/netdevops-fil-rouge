#!/bin/bash
# Cree le fichier de secrets chiffre playbooks/group_vars/all/vault.yml.
# Le mot de passe admin Grafana est genere aleatoirement.
set -euo pipefail
cd "$(dirname "$0")/.."

VAULT_FILE=playbooks/group_vars/all/vault.yml
if [ -f "${VAULT_FILE}" ]; then
    echo "${VAULT_FILE} existe deja. Pour le modifier : ansible-vault edit ${VAULT_FILE}"
    exit 1
fi

GRAFANA_PASSWORD=$(openssl rand -hex 12)
cat > "${VAULT_FILE}" <<VAULT
---
vault_grafana_admin_password: "${GRAFANA_PASSWORD}"
VAULT

echo "Choisis le mot de passe du coffre Ansible Vault (a reporter dans Jenkins) :"
ansible-vault encrypt "${VAULT_FILE}"
echo
echo "Coffre cree et chiffre : ${VAULT_FILE}"
echo "Mot de passe admin Grafana genere : ${GRAFANA_PASSWORD}"
echo "Note-le, puis : git add ${VAULT_FILE} && git commit -m 'Ajout du coffre chiffre'"
