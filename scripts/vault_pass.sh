#!/bin/sh
# Fournit le mot de passe Ansible Vault a partir de la variable
# d'environnement ANSIBLE_VAULT_PASSWORD (injectee par Jenkins).
if [ -z "${ANSIBLE_VAULT_PASSWORD:-}" ]; then
    echo "ANSIBLE_VAULT_PASSWORD non definie" >&2
    exit 1
fi
printf '%s\n' "${ANSIBLE_VAULT_PASSWORD}"
