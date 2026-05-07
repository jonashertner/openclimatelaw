#!/usr/bin/env bash
# Bootstrap a fresh Hetzner Ubuntu 24.04 VPS for OpenClimateLaw.
#
# Run once on a freshly-created VPS as root (or via sudo). Idempotent — safe to
# re-run if a step fails.
#
# Usage (on the VPS):
#   curl -fsSL https://raw.githubusercontent.com/jonashertner/openclimatelaw/master/deploy/bootstrap.sh -o bootstrap.sh
#   bash bootstrap.sh

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/jonashertner/openclimatelaw.git}"
APP_DIR="${APP_DIR:-/srv/openclimatelaw}"
BRANCH="${BRANCH:-master}"

require_root() {
    if [[ $EUID -ne 0 ]]; then
        echo "ERROR: run as root (or via sudo)." >&2
        exit 1
    fi
}

install_packages() {
    echo "==> apt update + base packages"
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -y
    apt-get install -y --no-install-recommends \
        ca-certificates curl gnupg lsb-release ufw git fail2ban
}

install_docker() {
    if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
        echo "==> Docker + compose plugin already installed"
        return
    fi
    echo "==> Installing Docker + compose plugin (official Docker apt repo)"
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
        gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    systemctl enable --now docker
}

configure_firewall() {
    echo "==> Configuring ufw (allow 22, 80, 443)"
    ufw --force reset >/dev/null
    ufw default deny incoming
    ufw default allow outgoing
    ufw allow 22/tcp comment "ssh"
    ufw allow 80/tcp comment "http (caddy)"
    ufw allow 443/tcp comment "https (caddy)"
    ufw allow 443/udp comment "http3 (caddy)"
    ufw --force enable
}

configure_fail2ban() {
    echo "==> Enabling fail2ban (default sshd jail)"
    systemctl enable --now fail2ban
}

clone_repo() {
    if [[ -d "$APP_DIR/.git" ]]; then
        echo "==> Repo already cloned at $APP_DIR; pulling latest from $BRANCH"
        git -C "$APP_DIR" fetch origin "$BRANCH"
        git -C "$APP_DIR" checkout "$BRANCH"
        git -C "$APP_DIR" pull --ff-only origin "$BRANCH"
    else
        echo "==> Cloning $REPO_URL → $APP_DIR (branch $BRANCH)"
        mkdir -p "$(dirname "$APP_DIR")"
        git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
    fi
}

setup_env_template() {
    if [[ ! -f "$APP_DIR/deploy/.env.production" ]]; then
        echo "==> Creating .env.production from example"
        cp "$APP_DIR/deploy/.env.production.example" "$APP_DIR/deploy/.env.production"
        local pw
        pw=$(openssl rand -base64 32 | tr -d '/+=' | head -c 40)
        sed -i "s|CHANGE_ME_TO_A_STRONG_RANDOM_VALUE|$pw|" "$APP_DIR/deploy/.env.production"
        chmod 600 "$APP_DIR/deploy/.env.production"
        echo "    Generated random POSTGRES_PASSWORD."
    else
        echo "==> .env.production already exists; leaving as-is"
    fi
}

main() {
    require_root
    install_packages
    install_docker
    configure_firewall
    configure_fail2ban
    clone_repo
    setup_env_template

    echo
    echo "==> Bootstrap complete."
    echo
    echo "Next steps (run from $APP_DIR/deploy):"
    echo "  cd $APP_DIR/deploy"
    echo "  docker compose -f compose.prod.yaml --env-file .env.production --profile migrate run --rm migrate"
    echo "  docker compose -f compose.prod.yaml --env-file .env.production up -d --build"
    echo
    echo "Once DNS for openclimatelaw.org and mcp.openclimatelaw.org points at this VPS,"
    echo "Caddy will obtain TLS certificates automatically (~30-60s)."
}

main "$@"
