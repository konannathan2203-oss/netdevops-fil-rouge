# Architecture technique

## Schéma

```mermaid
flowchart TB
    internet["Internet / utilisateurs"]
    admin["Poste admin<br/>Git, Jenkins, Grafana"]

    subgraph host["Hôte Docker - Ubuntu 24.04"]
        subgraph tools["Outils DevOps"]
            git["Dépôt Git (GitHub)"] -->|scrutation| jenkins["Jenkins"]
            jenkins -->|analyse| sonar["SonarQube"]
            jenkins -->|scan images| trivy["Trivy"]
            jenkins -->|ansible-playbook| ansible["Ansible"]
        end

        fw["router-fw<br/>nftables, policy DROP<br/>.1 dans chaque réseau"]

        subgraph dmz["dmz-net 172.20.1.0/24"]
            web["web-dmz<br/>Nginx :80/:443<br/>172.20.1.10"]
        end
        subgraph lan["lan-net 172.20.2.0/24"]
            dns["dns-lan<br/>dnsmasq :53<br/>172.20.2.10"]
            c1["client1 .100"]
            c2["client2 .101"]
        end
        subgraph mgmt["mgmt-net 172.20.3.0/24"]
            prom["Prometheus :9090 .10"]
            graf["Grafana :3000 .11"]
            node["node-exporter :9100 .12"]
            bb["blackbox .13"]
        end
    end

    internet -->|"HTTP/HTTPS → DNAT"| fw
    fw --> web
    c1 & c2 -->|DNS| dns
    c1 & c2 -->|"HTTP via routeur"| fw
    bb -->|"sondes via routeur"| fw
    prom --> node & bb
    graf --> prom
    ansible -->|"docker compose up"| fw
    admin --> jenkins & graf
```

## Choix techniques

| Sujet | Choix | Justification |
|---|---|---|
| Système hôte | Ubuntu 24.04 LTS | Noyau récent (nftables complet), support jusqu'en 2029 |
| Isolation des zones | 3 réseaux bridge Docker, passerelle Docker en `.254` | Le `.1` est laissé au routeur, comme sur le schéma du sujet |
| Routage inter-zones | Chaque conteneur a sa route par défaut vers `router-fw` (variable `NET_ROUTES`) | Tout le trafic inter-zones traverse le pare-feu |
| Pare-feu | nftables, chaînes `input` et `forward` en `policy drop` | « Tout est interdit sauf ce qui est autorisé » |
| Exposition Internet | Ports 80/443 publiés sur `router-fw`, puis DNAT vers `web-dmz` | Le serveur web n'est jamais exposé directement |
| Configuration | Ansible génère toutes les configurations (nftables, dnsmasq, Nginx, Prometheus, Compose) depuis des variables | Une seule source de vérité : `playbooks/group_vars/all/common.yml` |
| Environnements | Test (172.21.x) et prod (172.20.x) générés par les mêmes rôles | On teste exactement ce qui part en production, sur le même hôte |
| Secrets | Ansible Vault ; mot de passe fourni par un credential Jenkins | Aucun secret en clair dans Git |
| Supervision | Prometheus + node-exporter + blackbox exporter, Grafana provisionné | Les sondes blackbox passent par le pare-feu : elles vérifient les flux réels |

## Flux d'un déploiement

1. Un `git push` sur `main` est détecté par Jenkins (scrutation toutes les 5 minutes).
2. Jenkins lance le lint, puis l'analyse SonarQube.
3. Ansible génère les configurations de **test** et construit les 4 images, étiquetées avec le numéro de build.
4. Trivy analyse les images ; une CVE critique corrigeable bloque le pipeline.
5. Ansible déploie l'environnement de test et attend que router-fw, web-dmz et dns-lan soient *healthy*.
6. `tests/connectivity_test.py` vérifie toute la matrice des flux, puis l'environnement de test est supprimé.
7. Ansible déploie la **production** avec les mêmes images, puis les tests sont rejoués sur la prod.
8. En cas d'échec à n'importe quelle étape, un email est envoyé.
