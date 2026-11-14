#!/bin/bash
# Installe tous les outils du projet sur Ubuntu 24.04 LTS.
# Usage (depuis la racine du depot) : sudo ./scripts/install_tools.sh
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "A lancer avec sudo : sudo ./scripts/install_tools.sh" >&2
    exit 1
fi

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TARGET_USER="${SUDO_USER:-root}"
VENV=/opt/netdevops-venv
TRIVY_IMAGE=aquasec/trivy:0.69.3

step() { echo; echo "===== $* ====="; }

step "1/8 Paquets de base"
apt-get update
apt-get install -y ca-certificates curl gnupg git openssl jq unzip \
    python3 python3-venv python3-pip shellcheck nmap dnsutils \
    netcat-openbsd nftables fontconfig openjdk-21-jre

step "2/8 Ansible et linters (environnement Python dedie)"
python3 -m venv "${VENV}"
"${VENV}/bin/pip" install --upgrade pip
"${VENV}/bin/pip" install ansible-core ansible-lint yamllint pylint
for bin in ansible ansible-playbook ansible-vault ansible-galaxy ansible-lint yamllint pylint; do
    ln -sf "${VENV}/bin/${bin}" "/usr/local/bin/${bin}"
done

step "3/8 Docker Engine et Docker Compose"
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
# shellcheck disable=SC1091
CODENAME="$(. /etc/os-release && echo "${UBUNTU_CODENAME:-${VERSION_CODENAME}}")"
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
usermod -aG docker "${TARGET_USER}"

step "4/8 DNS fiable pour les conteneurs"
# Les images Alpine (musl) posent les questions IPv4 et IPv6 en meme temps
# et abandonnent si l'IPv6 echoue, ce que fait le DNS du NAT VMware.
# Relais dnsmasq sur docker0 : il transmet au resolveur d'Ubuntu et
# repond lui-meme "pas d'IPv6" (filter-AAAA).
apt-get install -y dnsmasq
cat > /etc/dnsmasq.d/docker.conf <<'DNSMASQ'
listen-address=172.17.0.1
bind-dynamic
no-resolv
server=127.0.0.53
filter-AAAA
cache-size=1000
DNSMASQ
systemctl enable dnsmasq
systemctl restart dnsmasq
echo '{ "dns": ["172.17.0.1"] }' > /etc/docker/daemon.json
systemctl restart docker

step "5/8 Jenkins LTS"
curl -fsSL https://pkg.jenkins.io/debian-stable/jenkins.io-2026.key -o /etc/apt/keyrings/jenkins-keyring.asc
echo "deb [signed-by=/etc/apt/keyrings/jenkins-keyring.asc] https://pkg.jenkins.io/debian-stable binary/" \
    > /etc/apt/sources.list.d/jenkins.list
apt-get update
apt-get install -y jenkins
usermod -aG docker jenkins
systemctl enable jenkins
systemctl restart jenkins

step "6/8 Reglages systeme pour SonarQube"
printf 'vm.max_map_count=524288\nfs.file-max=131072\n' > /etc/sysctl.d/99-sonarqube.conf
sysctl --system > /dev/null

step "7/8 SonarQube et image Trivy"
docker compose -f "${REPO_DIR}/tools/docker-compose.yml" up -d
# Version 0.69.3 : derniere version saine avant la compromission de mars 2026
docker pull "${TRIVY_IMAGE}"

step "8/8 Verifications"
docker run --rm alpine:3.22 sh -c "apk update > /dev/null && echo 'DNS des conteneurs : OK'" \
    || echo "ATTENTION : les conteneurs n'arrivent pas a telecharger des paquets (DNS)"
ansible --version | head -1
docker --version
docker compose version

IP="$(hostname -I | awk '{print $1}')"
echo
echo "Attente du mot de passe initial de Jenkins..."
for _ in $(seq 1 30); do
    [ -f /var/lib/jenkins/secrets/initialAdminPassword ] && break
    sleep 5
done
echo
echo "================================================================"
echo " Installation terminee"
echo " Jenkins   : http://${IP}:8080"
echo "   mot de passe initial : $(cat /var/lib/jenkins/secrets/initialAdminPassword 2>/dev/null || echo 'pas encore pret')"
echo " SonarQube : http://${IP}:9000  (admin / admin au premier lancement, 2 a 3 min)"
echo
echo " IMPORTANT : deconnecte-toi puis reconnecte-toi (ou 'newgrp docker')"
echo " pour que ${TARGET_USER} puisse utiliser docker sans sudo."
echo "================================================================"
