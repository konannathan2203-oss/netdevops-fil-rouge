# NetDevOps : automatisation et sécurisation d'une infrastructure réseau segmentée

Projet fil rouge DevOps, M1 Expert Réseau & Infrastructure Sécurisée.

Une PME découpe son réseau en trois zones isolées (DMZ, LAN, Management) reliées par un routeur-pare-feu nftables. Toute l'infrastructure est décrite dans ce dépôt (Infrastructure as Code), configurée par **Ansible**, conteneurisée avec **Docker**, déployée par **Jenkins**, analysée par **SonarQube** et **Trivy**, et supervisée par **Prometheus et Grafana**.

## Architecture

```
                         Internet (ports 80/443 de l'hôte)
                                     │ DNAT
┌────────────────────────────────────▼──────────────────────────────────────┐
│ Hôte Docker (Ubuntu 24.04)                                                 │
│                                                                            │
│  dmz-net 172.20.1.0/24        lan-net 172.20.2.0/24     mgmt-net 172.20.3.0/24
│  ┌─────────────┐              ┌─────────────┐           ┌──────────────────┐
│  │ web-dmz     │              │ dns-lan     │           │ prometheus  .10  │
│  │ Nginx .10   │              │ dnsmasq .10 │           │ grafana     .11  │
│  └──────┬──────┘              │ client1 .100│           │ node-export .12  │
│         │                     │ client2 .101│           │ blackbox    .13  │
│         │                     └──────┬──────┘           └────────┬─────────┘
│         │ .1                         │ .1                        │ .1
│         └──────────────┬─────────────┴──────────────┬────────────┘
│                  ┌─────┴──────────────────────────────┐
│                  │ router-fw (nftables, politique DROP)│
│                  └─────────────────────────────────────┘
│                                                                            │
│  Outils DevOps : Git ─▶ Jenkins ─▶ SonarQube ─▶ Trivy ─▶ déploiement       │
└────────────────────────────────────────────────────────────────────────────┘
```

Détails : [docs/architecture.md](docs/architecture.md) · Matrice des flux : [docs/matrice-flux.md](docs/matrice-flux.md)

| Service | Image | Réseau | Adresse (prod) | Rôle |
|---|---|---|---|---|
| router-fw | `netdevops/router-fw` (Alpine + nftables) | les 3 | .1 dans chaque réseau | Routage inter-zones, filtrage, DNAT |
| web-dmz | `netdevops/web-dmz` (Nginx 1.28) | dmz-net | 172.20.1.10 | Site public HTTP/HTTPS |
| dns-lan | `netdevops/dns-lan` (dnsmasq) | lan-net | 172.20.2.10 | DNS interne `entreprise.local` |
| client1 / client2 | `netdevops/client` | lan-net | 172.20.2.100 / .101 | Postes de test (curl, dig, nmap) |
| prometheus | `prom/prometheus:v3.5.0` | mgmt-net | 172.20.3.10 | Collecte des métriques |
| grafana | `grafana/grafana:12.1.0` | mgmt-net | 172.20.3.11 | Dashboards |
| node-exporter | `prom/node-exporter:v1.9.1` | mgmt-net | 172.20.3.12 | Métriques système de l'hôte |
| blackbox | `prom/blackbox-exporter:v0.27.0` | mgmt-net | 172.20.3.13 | Sondes HTTP, HTTPS et DNS à travers le pare-feu |

Deux environnements sont générés à partir des mêmes rôles :

| | Test | Production |
|---|---|---|
| Sous-réseaux | 172.21.1-3.0/24 | 172.20.1-3.0/24 (plan du sujet) |
| Site web | ports 18080 / 18443 | ports 80 / 443 |
| Prometheus / Grafana | 19090 / 13000 | 9090 / 3000 |

## Arborescence

```
.
├── Jenkinsfile                  Pipeline CI/CD (9 étapes)
├── ansible.cfg
├── inventories/{test,prod}/     Variables propres à chaque environnement
├── playbooks/
│   ├── site.yml                 Génération des configs, build, déploiement
│   ├── destroy.yml              Suppression d'un environnement
│   └── group_vars/all/
│       ├── common.yml           Plan d'adressage, matrice des flux, versions
│       └── vault.yml            Secrets chiffrés (Ansible Vault)
├── roles/
│   ├── router_fw/               Template nftables généré depuis la matrice des flux
│   ├── dns_lan/                 Template dnsmasq
│   ├── web_dmz/                 Template Nginx, page, certificat TLS
│   ├── monitoring/              Prometheus, blackbox, Grafana + dashboard JSON
│   └── compose_deploy/          Template docker-compose.yml, build, déploiement
├── docker/                      Dockerfiles des 4 images maison
├── tests/connectivity_test.py   Tests de connectivité et de filtrage
├── scripts/                     Installation, coffre Vault
├── tools/docker-compose.yml     SonarQube
└── docs/                        Architecture, flux, audit sécurité, démo
```

## Installation sur Ubuntu 24.04

Prérequis : VM Ubuntu 24.04, 6 Go de RAM, 4 vCPU, 40 Go de disque, accès Internet.

```bash
# 1. Récupérer le dépôt
git clone https://github.com/<ton-compte>/netdevops-fil-rouge.git
cd netdevops-fil-rouge

# 2. Installer Docker, Ansible, linters, Jenkins, SonarQube, Trivy
sudo ./scripts/install_tools.sh
newgrp docker            # ou se déconnecter / reconnecter

# 3. Créer le coffre de secrets (mot de passe Grafana chiffré)
./scripts/init_vault.sh
git add playbooks/group_vars/all/vault.yml && git commit -m "Coffre Ansible Vault" && git push
```

## Utilisation manuelle (sans Jenkins)

```bash
# Déployer l'environnement de test
ansible-playbook -i inventories/test playbooks/site.yml --ask-vault-pass

# Tester la matrice des flux
python3 tests/connectivity_test.py --env test

# Déployer la production
ansible-playbook -i inventories/prod playbooks/site.yml --ask-vault-pass

# Supprimer un environnement
ansible-playbook -i inventories/test playbooks/destroy.yml --ask-vault-pass
```

Commandes utiles :

```bash
docker exec prod-router-fw nft list ruleset           # règles et compteurs du pare-feu
docker exec prod-client1 dig @172.20.2.10 web.entreprise.local
docker exec prod-client1 nmap -Pn -sT -p 22,80,443 172.20.1.10
docker exec prod-web-dmz nc -zv -w 3 172.20.2.10 53   # DMZ -> LAN : doit échouer
```

## Pipeline Jenkins

| # | Étape | Outil | Bloque le pipeline si… |
|---|---|---|---|
| 1 | Checkout | Git | le dépôt est inaccessible |
| 2 | Lint | yamllint, ansible-lint (profil production), pylint, shellcheck | une erreur de style ou de bonne pratique |
| 3 | SonarQube Scan | sonar-scanner (Docker) | l'analyse échoue |
| 4 | Build Docker | Ansible + Docker Compose | une image ne se construit pas |
| 5 | Trivy Scan | Trivy 0.69.3 | une CVE **critique corrigeable** est présente |
| 6 | Déploiement test | Ansible | un service critique n'est pas *healthy* |
| 7 | Tests de connectivité | `tests/connectivity_test.py` (nc, dig, nmap, curl, nft, API Prometheus) | un flux ne respecte pas la matrice |
| 8 | Déploiement prod | Ansible (branche `main` uniquement) | les tests de fumée échouent |
| 9 | Notification | email (Mailer) | — |

Rapports archivés à chaque build : `reports/trivy-*.txt`, `reports/connectivity-*.xml` (onglet *Test Results*), `reports/nftables-test.txt`.

### Configuration de Jenkins

1. Ouvrir `http://<IP>:8080`, saisir le mot de passe initial, installer les plugins suggérés.
2. SonarQube (`http://<IP>:9000`) : se connecter (`admin`/`admin`), puis *My Account → Security → Generate Token* (type *Global Analysis Token*).
3. Jenkins → *Administrer Jenkins → Credentials → System → Identifiants globaux → Add Credentials* :
   - *Secret text*, ID **`ansible-vault-pass`** : le mot de passe du coffre Ansible Vault ;
   - *Secret text*, ID **`sonar-token`** : le jeton SonarQube.
4. *Nouveau Item* → **Pipeline** → *Pipeline script from SCM* → Git → URL du dépôt → branche `*/main` → *Script Path* `Jenkinsfile`.
5. *Lancer un build*. Les suivants partent automatiquement (scrutation du dépôt toutes les 5 minutes).

## Branches Git

| Branche | Usage |
|---|---|
| `main` | Code validé. Le pipeline déploie en production. |
| `develop` | Intégration. Le pipeline teste sans déployer en production. |
| `feature/*` | Une branche par évolution, fusionnée dans `develop` |

## Livrables

| Livrable demandé | Emplacement |
|---|---|
| Dépôt Git avec historique et branches | ce dépôt (`main`, `develop`) |
| Playbooks Ansible (rôles, variables, templates) | `playbooks/`, `roles/`, `inventories/` |
| Fichiers Docker et Docker Compose | `docker/`, `roles/compose_deploy/templates/docker-compose.yml.j2`, `tools/docker-compose.yml` |
| Jenkinsfile versionné | `Jenkinsfile` |
| Rapports SonarQube et Trivy | SonarQube `http://<IP>:9000`, artefacts Jenkins `reports/trivy-*.txt` |
| Dashboards Grafana exportés (JSON) | `roles/monitoring/files/dashboards/netdevops-reseau.json` |
| Documentation technique | ce README, `docs/` |
| Rapport d'audit sécurité | [docs/rapport-audit-securite.md](docs/rapport-audit-securite.md) |
| Présentation et démo | [docs/guide-demo.md](docs/guide-demo.md) |
