# Rapport d'audit sécurité

Périmètre : infrastructure NetDevOps (router-fw, web-dmz, dns-lan, clients, supervision) et chaîne CI/CD (Git, Jenkins, SonarQube, Trivy, Ansible).

> Les sections **Résultats Trivy** et **Résultats SonarQube** sont à compléter avec les chiffres de ton dernier build (artefacts Jenkins `reports/trivy-*.txt` et tableau de bord SonarQube).

## 1. Mesures de sécurité en place

| Domaine | Mesure | Où |
|---|---|---|
| Segmentation | 3 zones isolées (DMZ, LAN, Management), trafic inter-zones forcé via router-fw | `docker-compose.yml.j2`, `NET_ROUTES` |
| Filtrage | nftables en `policy drop` sur `input` et `forward`, liste blanche issue de la matrice des flux | `roles/router_fw` |
| Exposition | Seuls 80/443 publiés, via DNAT ; DNS et supervision non exposés sur Internet | `fw_dnat_ports` |
| Anti-rebond | DMZ → LAN et DMZ → Internet bloqués (limite l'impact d'une compromission du serveur web) | matrice des flux, règles 9 et 10 |
| Anti-flood | ICMP limité à 10 paquets/s ; états `invalid` rejetés | `nftables.conf.j2` |
| Journalisation | Compteurs et préfixes de log sur tous les rejets | `nftables.conf.j2` |
| DNS | `domain-needed`, `bogus-priv`, `stop-dns-rebind`, domaine local jamais transmis vers Internet | `dnsmasq.conf.j2` |
| Web | `server_tokens off`, TLS 1.2/1.3 uniquement, en-têtes HSTS, CSP, X-Frame-Options, nosniff ; `/nginx_status` réservé au Management | `nginx.conf.j2` |
| Secrets | Mot de passe Grafana dans Ansible Vault ; mot de passe du coffre dans un credential Jenkins | `scripts/init_vault.sh` |
| Clé TLS | Générée par Ansible hors de l'image, droits 0600, montée en lecture seule | `roles/web_dmz` |
| Conteneurs | `no-new-privileges`, router-fw en `cap_drop: ALL` + `NET_ADMIN`/`NET_RAW`, configurations en lecture seule, rotation des logs | `docker-compose.yml.j2` |
| Supply chain | Images tierces épinglées ; Trivy épinglé en 0.69.3 (version saine antérieure à la compromission de mars 2026) | `common.yml`, `Jenkinsfile` |
| Qualité | Lint (profil ansible-lint *production*), SonarQube, tests automatisés de la matrice des flux avant toute mise en production | `Jenkinsfile` |

## 2. Résultats Trivy (à compléter)

| Image | CVE critiques | CVE hautes | Commentaire |
|---|---|---|---|
| netdevops/router-fw | … | … | |
| netdevops/web-dmz | … | … | |
| netdevops/dns-lan | … | … | |
| netdevops/client | … | … | |

Le pipeline bloque si une CVE **critique corrigeable** est détectée (`--severity CRITICAL --ignore-unfixed --exit-code 1`).

## 3. Résultats SonarQube (à compléter)

| Indicateur | Valeur |
|---|---|
| Quality Gate | … |
| Bugs | … |
| Vulnérabilités | … |
| Security Hotspots | … |
| Code smells | … |

## 4. Points faibles identifiés et corrections proposées

| # | Point faible | Risque | Gravité | Correction proposée |
|---|---|---|---|---|
| 1 | web-dmz, dns-lan et les clients ont la capacité `NET_ADMIN` (pour poser leur route vers le routeur) | Un attaquant root dans le conteneur pourrait modifier ses routes et contourner le routeur via la passerelle Docker | Moyenne | Poser les routes avec un conteneur « sidecar » éphémère (déjà fait pour le blackbox) et retirer `NET_ADMIN` des services ; ou réseaux Docker `internal: true` |
| 2 | Le mot de passe Grafana est passé en variable d'environnement | Lisible avec `docker inspect` par un utilisateur du groupe docker | Moyenne | Utiliser `GF_SECURITY_ADMIN_PASSWORD__FILE` avec un secret Docker |
| 3 | Prometheus (9090) est publié sans authentification | Fuite d'informations sur l'infrastructure | Moyenne | Publier sur `127.0.0.1` uniquement, ou ajouter un reverse proxy avec authentification |
| 4 | Certificat TLS auto-signé | Avertissement navigateur, pas d'authentification du serveur | Faible (lab) | Certificat d'une AC interne ou Let's Encrypt en production réelle |
| 5 | Les conteneurs router-fw, web-dmz et dns-lan tournent en root | Impact accru en cas d'évasion | Moyenne | Utilisateurs non-root, `read_only: true` avec `tmpfs` pour les dossiers d'écriture |
| 6 | Les logs nftables d'un conteneur ne remontent dans le journal de l'hôte qu'avec `net.netfilter.nf_log_all_netns=1` | Rejets visibles seulement via les compteurs | Faible | Activer ce sysctl sur l'hôte, ou centraliser avec ELK/Loki (variante du sujet) |
| 7 | Jenkins a accès au socket Docker (groupe `docker`) | Équivaut à un accès root à l'hôte si Jenkins est compromis | Haute | Agents Jenkins dédiés, Docker rootless, ou Kaniko/Buildah pour les builds |
| 8 | Pas de signature des images | Une image modifiée sur l'hôte ne serait pas détectée | Moyenne | Signature avec Cosign, vérification avant déploiement |
| 9 | Notification uniquement par email (SMTP à configurer) | Échecs non vus | Faible | Webhook Slack/Teams |

## 5. Conclusion

L'infrastructure applique le principe du moindre privilège au niveau réseau : seuls les flux nécessaires sont ouverts, la DMZ est isolée du LAN et d'Internet, et la supervision reste confinée au réseau de management. La chaîne CI/CD empêche le déploiement d'une configuration qui ne respecte pas la matrice des flux ou d'une image présentant une vulnérabilité critique corrigeable.

Priorités de correction : **7** (accès Jenkins au socket Docker), puis **1** et **5** (privilèges des conteneurs), puis **2** et **3** (secrets et exposition de la supervision).
