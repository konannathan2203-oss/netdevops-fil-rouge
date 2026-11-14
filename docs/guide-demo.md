# Guide de présentation (15 min) et démo

## Déroulé

| Durée | Partie | Contenu |
|---|---|---|
| 2 min | Contexte | La PME, les 3 zones, l'objectif : automatiser et sécuriser |
| 3 min | Architecture | Schéma (`docs/architecture.md`), plan d'adressage, matrice des flux |
| 2 min | Infrastructure as Code | Les variables `common.yml` → templates Ansible → configs générées |
| 5 min | Démo | Voir ci-dessous |
| 2 min | Sécurité | Mesures en place, rapport Trivy/SonarQube, points faibles et corrections |
| 1 min | Conclusion | Ce qui marche, ce qu'on améliorerait (ELK, GNS3, Cosign) |

## Démo pas à pas

Préparer avant l'oral : la VM allumée, la prod déjà déployée, Jenkins, SonarQube et Grafana ouverts dans des onglets.

**1. Une modification déclenche le pipeline.** Modifier le texte de `roles/web_dmz/templates/index.html.j2`, puis :

```bash
git commit -am "Demo : modification de la page" && git push
```

Dans Jenkins, cliquer sur *Lancer un build* (ou attendre la scrutation) et montrer les 9 étapes.

**2. Le pare-feu en action** (pendant que le pipeline tourne) :

```bash
docker exec prod-router-fw nft list ruleset | head -40
docker exec prod-client1 curl -s http://172.20.1.10 | grep marker     # LAN -> DMZ : OK
docker exec prod-client1 dig +short @172.20.2.10 web.entreprise.local # DNS interne : OK
docker exec prod-client1 nmap -Pn -sT -p 22,80,443 172.20.1.10        # 22 filtré
docker exec prod-web-dmz nc -zv -w 3 172.20.2.10 53                   # DMZ -> LAN : bloqué
docker exec prod-router-fw nft list chain inet filter forward | grep DROP  # compteur de rejets
```

**3. Résultats du pipeline** : onglet *Test Results* (tests de connectivité), artefacts `trivy-*.txt`, projet dans SonarQube.

**4. Supervision** : Grafana `http://<IP>:3000`, dossier *NetDevOps*, dashboard *Supervision réseau*.

**5. Le site publié** : `http://<IP>` depuis le navigateur Windows, puis `https://<IP>`.

## Questions probables

- **Pourquoi le `.1` n'est-il pas la passerelle Docker ?** Pour le laisser au routeur, comme dans le sujet. La passerelle Docker est en `.254` et ne sert qu'à la sortie du routeur.
- **Comment le trafic passe-t-il par le routeur ?** Chaque conteneur reçoit une route par défaut vers router-fw au démarrage (`docker/common/netinit.sh`).
- **Pourquoi deux environnements ?** On teste exactement les mêmes images et les mêmes rôles que la production, sur des sous-réseaux différents (172.21.x), avant de déployer.
- **Comment sont gérés les secrets ?** Ansible Vault ; le mot de passe du coffre est un credential Jenkins, jamais dans Git.
- **Pourquoi Trivy en 0.69.3 ?** Les versions 0.69.4 à 0.69.6 ont été compromises en mars 2026 (attaque supply chain) ; on épingle la dernière version saine.
