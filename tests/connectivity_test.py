#!/usr/bin/env python3
"""Tests de connectivite et de filtrage de l'infrastructure NetDevOps.

Verifie que la matrice des flux est respectee une fois l'environnement
deploye : flux autorises ouverts, flux interdits bloques par router-fw,
resolution DNS interne et supervision operationnelle.

Usage :
    python3 tests/connectivity_test.py --env test
Le plan de test (noms des conteneurs, IP, ports) est genere par Ansible
dans build/<env>/connectivity.json.
"""

import argparse
import json
import ssl
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

REPO_ROOT = Path(__file__).resolve().parent.parent
WEB_MARKER = "NETDEVOPS-WEB-OK"
CMD_TIMEOUT = 20


@dataclass
class TestResult:
    """Resultat d'un test unitaire de connectivite."""

    name: str
    passed: bool
    detail: str


def run(command):
    """Execute une commande et renvoie (code retour, sortie standard)."""
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=CMD_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    return completed.returncode, (completed.stdout + completed.stderr).strip()


def docker_exec(container, *args):
    """Execute une commande dans un conteneur."""
    return run(["docker", "exec", container, *args])


def tcp_reachable(container, ip_address, port):
    """Teste l'ouverture d'une connexion TCP depuis un conteneur."""
    code, _ = docker_exec(container, "nc", "-z", "-w", "3", ip_address, str(port))
    return code == 0


def http_get(url):
    """Recupere le contenu d'une URL (certificat auto-signe accepte)."""
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(url, timeout=10, context=context) as response:
        return response.status, response.read().decode("utf-8", errors="replace")


class ConnectivitySuite:
    """Suite de tests construite a partir du plan genere par Ansible."""

    def __init__(self, plan):
        self.plan = plan
        self.ctr = plan["containers"]
        self.ips = plan["ips"]
        self.ports = plan["published_ports"]
        self.results = []

    def record(self, name, passed, detail=""):
        """Enregistre et affiche le resultat d'un test."""
        self.results.append(TestResult(name, passed, detail))
        status = "OK  " if passed else "FAIL"
        print(f"[{status}] {name} {('- ' + detail) if detail else ''}")

    def expect_tcp(self, name, container, ip_address, port, allowed):
        """Verifie qu'un flux TCP est autorise ou bloque."""
        reachable = tcp_reachable(container, ip_address, port)
        expected = "autorise" if allowed else "bloque"
        observed = "ouvert" if reachable else "ferme/filtre"
        self.record(name, reachable == allowed, f"attendu {expected}, observe {observed}")

    def test_internet_to_dmz(self):
        """Internet -> routeur (DNAT) -> web-dmz en HTTP et HTTPS."""
        for scheme, port in (("http", self.ports["http"]), ("https", self.ports["https"])):
            name = f"Internet -> web-dmz en {scheme.upper()} (DNAT router-fw)"
            try:
                status, body = http_get(f"{scheme}://127.0.0.1:{port}/")
                self.record(name, status == 200 and WEB_MARKER in body, f"HTTP {status}")
            except OSError as error:
                self.record(name, False, str(error))

    def test_internet_to_dns_closed(self):
        """Le DNS interne ne doit pas etre publie sur Internet."""
        _, output = run(["docker", "port", self.ctr["router"]])
        self.record("Internet -> dns-lan bloque (aucun port 53 publie)", "53/" not in output, output.replace("\n", ", "))

    def test_lan_flows(self):
        """Flux depuis un poste client du LAN."""
        client = self.ctr["client"]
        self.expect_tcp("LAN -> web-dmz:80", client, self.ips["web_dmz"], 80, True)
        self.expect_tcp("LAN -> web-dmz:443", client, self.ips["web_dmz"], 443, True)
        self.expect_tcp("LAN -> web-dmz:22 (non autorise)", client, self.ips["web_dmz"], 22, False)
        self.expect_tcp("LAN -> Grafana:3000 (Management interdit)", client, self.ips["grafana"], 3000, False)

    def test_dns_resolution(self):
        """Resolution d'un nom interne par dns-lan."""
        name = f"web.{self.plan['dns_domain']}"
        _, output = docker_exec(self.ctr["client"], "dig", "+short", "+time=3", f"@{self.ips['dns_lan']}", name)
        self.record(f"LAN -> dns-lan resout {name}", self.ips["web_dmz"] in output.split(), output or "aucune reponse")

    def test_dmz_isolation(self):
        """Un serveur de la DMZ compromis ne doit atteindre ni le LAN ni Internet."""
        web = self.ctr["web"]
        self.expect_tcp("DMZ -> dns-lan:53 (rebond vers le LAN)", web, self.ips["dns_lan"], 53, False)
        self.expect_tcp("DMZ -> Internet 1.1.1.1:443 (exfiltration)", web, "1.1.1.1", 443, False)

    def test_nmap_scan(self):
        """Scan nmap du serveur web depuis le LAN : seuls 80 et 443 ouverts."""
        _, output = docker_exec(self.ctr["client"], "nmap", "-Pn", "-sT", "-p", "22,80,443", self.ips["web_dmz"])
        states = {}
        for line in output.splitlines():
            fields = line.split()
            if len(fields) >= 2 and fields[0].endswith("/tcp"):
                states[fields[0]] = fields[1]
        passed = states.get("80/tcp") == "open" and states.get("443/tcp") == "open" and states.get("22/tcp") != "open"
        summary = ", ".join(f"{port} {state}" for port, state in states.items())
        self.record("Scan nmap LAN -> web-dmz (22 filtre, 80/443 ouverts)", passed, summary)

    def test_firewall_policy(self):
        """Les chaines input et forward du routeur sont en politique DROP."""
        _, output = docker_exec(self.ctr["router"], "nft", "list", "table", "inet", "filter")
        passed = output.count("policy drop") >= 2
        self.record("router-fw : politique par defaut DROP (input et forward)", passed)

    def test_monitoring(self, wait_seconds=90):
        """Prometheus voit toutes ses sondes et cibles en etat UP."""
        url = f"http://127.0.0.1:{self.ports['prometheus']}/api/v1/query?query=probe_success"
        deadline = time.time() + wait_seconds
        detail = ""
        while time.time() < deadline:
            try:
                _, body = http_get(url)
                series = json.loads(body)["data"]["result"]
                values = {s["metric"].get("job", "?"): s["value"][1] for s in series}
                detail = str(values)
                if len(values) >= 3 and all(value == "1" for value in values.values()):
                    self.record("Supervision : sondes blackbox UP (web HTTP/HTTPS, DNS)", True, detail)
                    return
            except (OSError, ValueError, KeyError) as error:
                detail = str(error)
            time.sleep(10)
        self.record("Supervision : sondes blackbox UP (web HTTP/HTTPS, DNS)", False, detail)

    def run_all(self, skip_monitoring=False):
        """Lance tous les tests."""
        self.test_firewall_policy()
        self.test_internet_to_dmz()
        self.test_internet_to_dns_closed()
        self.test_lan_flows()
        self.test_dns_resolution()
        self.test_dmz_isolation()
        self.test_nmap_scan()
        if not skip_monitoring:
            self.test_monitoring()
        return all(result.passed for result in self.results)

    def write_junit(self, path):
        """Ecrit un rapport JUnit lisible par Jenkins."""
        failures = sum(1 for result in self.results if not result.passed)
        suite = ElementTree.Element(
            "testsuite",
            name=f"connectivite-{self.plan['environment']}",
            tests=str(len(self.results)),
            failures=str(failures),
        )
        for result in self.results:
            case = ElementTree.SubElement(suite, "testcase", classname="netdevops.connectivite", name=result.name)
            if not result.passed:
                failure = ElementTree.SubElement(case, "failure", message=result.detail)
                failure.text = result.detail
        path.parent.mkdir(parents=True, exist_ok=True)
        ElementTree.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def main():
    """Point d'entree."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--env", default="test", choices=["test", "prod"])
    parser.add_argument("--skip-monitoring", action="store_true")
    parser.add_argument("--junit", default=None, help="chemin du rapport JUnit")
    args = parser.parse_args()

    plan_file = REPO_ROOT / "build" / args.env / "connectivity.json"
    plan = json.loads(plan_file.read_text(encoding="utf-8"))
    suite = ConnectivitySuite(plan)
    success = suite.run_all(skip_monitoring=args.skip_monitoring)

    junit = Path(args.junit) if args.junit else REPO_ROOT / "reports" / f"connectivity-{args.env}.xml"
    suite.write_junit(junit)
    passed = sum(1 for result in suite.results if result.passed)
    print(f"\n{passed}/{len(suite.results)} tests reussis - rapport : {junit}")
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
