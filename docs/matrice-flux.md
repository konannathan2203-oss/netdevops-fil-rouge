# Matrice des flux

Politique par défaut du routeur : **DROP** (chaînes `input` et `forward`). Seuls les flux ci-dessous sont autorisés ; tout le reste est bloqué et compté (`counter log prefix "FW-FORWARD-DROP"`).

La source de vérité est la variable `fw_forward_rules` dans `playbooks/group_vars/all/common.yml`. Le fichier `nftables.conf` est généré à partir d'elle par le rôle `router_fw`.

| # | Source | Destination | Service | Décision | Justification | Vérifié par |
|---|---|---|---|---|---|---|
| 1 | Internet | web-dmz (via DNAT du routeur) | TCP 80, 443 | **Autorisé** | Seul service public de l'entreprise | `test_internet_to_dmz` |
| 2 | Internet | dns-lan | 53 | **Bloqué** | Le DNS interne ne doit pas être exposé (fuite d'informations, amplification DDoS) | `test_internet_to_dns_closed` |
| 3 | Clients LAN | dns-lan | UDP/TCP 53 | **Autorisé** | Même réseau, pas de passage par le routeur | `test_dns_resolution` |
| 4 | Clients LAN | web-dmz | TCP 80, 443 | **Autorisé** | Les employés consultent le site de l'entreprise | `test_lan_flows` |
| 5 | Clients LAN | web-dmz | autres ports (ex. 22) | **Bloqué** | Moindre privilège | `test_lan_flows`, `test_nmap_scan` |
| 6 | Clients LAN | Internet | TCP 80, 443 | **Autorisé** | Navigation des employés (avec NAT) | simulation |
| 7 | dns-lan | résolveurs publics | UDP/TCP 53 | **Autorisé** | Résolution des noms externes | simulation |
| 8 | Clients LAN | Management (Grafana 3000…) | tout | **Bloqué** | La supervision est réservée aux administrateurs | `test_lan_flows` |
| 9 | web-dmz | LAN (dns-lan, clients) | tout | **Bloqué** | Un serveur DMZ compromis ne doit pas pouvoir rebondir vers le réseau interne | `test_dmz_isolation` |
| 10 | web-dmz | Internet | tout | **Bloqué** | Empêche l'exfiltration de données et le téléchargement d'outils d'attaque | `test_dmz_isolation` |
| 11 | Management | toutes zones | tout | **Autorisé** | Supervision (sondes blackbox) et administration | `test_monitoring` |
| 12 | Toutes zones internes | router-fw | ICMP echo (10/s) | **Autorisé** | Diagnostic, limité contre le flood | — |
| 13 | Tout le reste | — | — | **Bloqué** | Politique par défaut | compteurs nftables |

Ces 13 règles ont été validées avant déploiement par une simulation à base de *network namespaces* Linux (même fichier `nftables.conf`, 14 cas de test, 14 réussis).
