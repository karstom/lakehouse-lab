# shellcheck shell=bash
# Prerequisite checks: Docker, Compose v2, RAM, disk, WSL2, ports.
# Hard failures return non-zero; resource shortfalls only warn.

# Minimum-requirement thresholds for the HOST's tools, not pins of anything the lab runs
# or builds, so they live here rather than in versions.env (documented ADR-012 exemption;
# see the "Not pins" note in tools/check_versions.py).
LAB_MIN_DOCKER="24.0.0"
LAB_MIN_COMPOSE="2.20.0"   # compose.yaml uses top-level include:, added in 2.20
LAB_RAM_RECOMMENDED_GB=16  # core fits a 16 GB machine (CONTRACT.md: <= 10 GB of limits)
LAB_RAM_MIN_GB=8
LAB_RAM_MIN_GB_ENGINEER=12 # engineer adds Spark master, worker and Spark Connect (fits 16 GB)
LAB_DISK_MIN_GB=20

# is_wsl [PROC_VERSION_FILE] -> 0 when running under WSL (1 or 2).
is_wsl() {
  local f=${1:-/proc/version}
  [ -n "${WSL_DISTRO_NAME:-}" ] && return 0
  [ -r "$f" ] && grep -qi 'microsoft' "$f"
}

check_docker() {
  local v
  command -v docker >/dev/null 2>&1 || {
    err "docker is not installed."
    info "  Install Docker Engine: https://docs.docker.com/engine/install/"
    is_wsl && info "  On WSL2: install Docker Desktop with WSL integration for this distro, or Docker Engine inside the distro."
    return 1
  }
  if ! v=$(docker version --format '{{.Server.Version}}' 2>/dev/null) || [ -z "$v" ]; then
    err "cannot talk to the Docker daemon."
    info "  Is it running? Can this user use it? (add yourself to the 'docker' group, then log in again)"
    is_wsl && info "  On WSL2 with Docker Desktop: Settings -> Resources -> WSL integration -> enable this distro."
    return 1
  fi
  if ! version_ge "$v" "$LAB_MIN_DOCKER"; then
    err "Docker $v is too old; need >= $LAB_MIN_DOCKER."
    return 1
  fi
  ok "Docker $v"
}

check_compose() {
  local v
  if ! v=$(docker compose version --short 2>/dev/null) || [ -z "$v" ]; then
    err "Docker Compose v2 plugin ('docker compose') not found. The old 'docker-compose' v1 is not supported."
    info "  Install: https://docs.docker.com/compose/install/linux/"
    return 1
  fi
  v=${v#v}
  if ! version_ge "$v" "$LAB_MIN_COMPOSE"; then
    err "Docker Compose $v is too old; need >= $LAB_MIN_COMPOSE."
    return 1
  fi
  ok "Docker Compose $v"
}

check_tools() {
  local t missing=""
  for t in openssl awk; do
    command -v "$t" >/dev/null 2>&1 || missing="$missing $t"
  done
  if [ -n "$missing" ]; then
    err "missing required tools:$missing"
    return 1
  fi
}

# Memory as Docker sees it (the Docker Desktop / WSL2 VM, not the Windows host).
docker_mem_gb() {
  local bytes
  bytes=$(docker info --format '{{.MemTotal}}' 2>/dev/null || true)
  if ! [[ "$bytes" =~ ^[0-9]+$ ]] || [ "$bytes" -eq 0 ]; then
    bytes=$(awk '/^MemTotal:/ {print $2 * 1024}' /proc/meminfo 2>/dev/null || echo 0)
  fi
  printf '%s\n' $(( (bytes + 536870912) / 1073741824 ))
}

check_memory() {
  local gb
  gb=$(docker_mem_gb)
  if [ "$gb" -lt "$LAB_RAM_MIN_GB" ]; then
    warn "Docker has ${gb} GB of RAM. The core profile wants ${LAB_RAM_RECOMMENDED_GB} GB; below ${LAB_RAM_MIN_GB} GB services may be OOM-killed."
    is_wsl && wsl_memory_hint
  elif [ "$gb" -lt "$LAB_RAM_RECOMMENDED_GB" ]; then
    warn "Docker has ${gb} GB of RAM; ${LAB_RAM_RECOMMENDED_GB} GB is recommended for the core profile. It should start, but leave little headroom."
    is_wsl && wsl_memory_hint
  else
    ok "Memory: ${gb} GB available to Docker"
  fi
}

# check_profile_memory PROFILE -> warn when the chosen profile needs more than core.
check_profile_memory() {
  local gb
  [ "$1" = engineer ] || return 0
  gb=$(docker_mem_gb)
  if [ "$gb" -lt "$LAB_RAM_MIN_GB_ENGINEER" ]; then
    warn "profile engineer (Spark) wants ${LAB_RAM_RECOMMENDED_GB} GB of RAM; Docker has ${gb} GB. Below ${LAB_RAM_MIN_GB_ENGINEER} GB Spark may be OOM-killed; consider --profile core."
    is_wsl && wsl_memory_hint
  fi
  return 0
}

wsl_memory_hint() {
  info "  WSL2 caps the VM's memory (default: half of Windows RAM). To raise it, put this in"
  info "  %UserProfile%\\.wslconfig on Windows, then run 'wsl --shutdown':"
  info "      [wsl2]"
  info "      memory=12GB"
}

check_disk() {
  local path=$1 kb gb
  kb=$(df -Pk "$path" 2>/dev/null | awk 'NR==2 {print $4}')
  [[ "$kb" =~ ^[0-9]+$ ]] || { warn "could not read free disk space for $path"; return 0; }
  gb=$((kb / 1048576))
  if [ "$gb" -lt "$LAB_DISK_MIN_GB" ]; then
    warn "only ${gb} GB free on $(df -P "$path" | awk 'NR==2 {print $6}'); images and data want at least ${LAB_DISK_MIN_GB} GB."
  else
    ok "Disk: ${gb} GB free for $path"
  fi
}

# WSL2 guidance: where the repo lives and how browsers on Windows reach the lab.
check_wsl() {
  is_wsl || return 0
  info "Detected WSL2."
  case "$V3_DIR" in
    /mnt/[a-z]/*)
      warn "the lab is on a Windows drive ($V3_DIR). Bind mounts are slow there and"
      warn "file modes (chmod 600 on .secrets.env and the CA key) are not enforced."
      warn "Clone the repo inside the Linux filesystem instead (e.g. ~/lakehouse-lab)."
      ;;
  esac
  info "  Browsers on Windows reach *.lab.localhost through WSL's localhost forwarding."
  info "  Trust the lab CA in Windows (not only in Linux); './lab ca' prints the command."
}

# check_port PORT -> warn when something other than this project already listens on it.
check_port() {
  local port=$1 owner
  if command -v ss >/dev/null 2>&1; then
    ss -Hltn "sport = :$port" 2>/dev/null | grep -q . || return 0
  else
    return 0
  fi
  owner=$(docker ps --filter "publish=$port" --format '{{.Label "com.docker.compose.project"}}' 2>/dev/null | head -n1)
  if [ -n "$owner" ] && [ "$owner" = "$COMPOSE_PROJECT_NAME" ]; then
    return 0
  fi
  local by=""
  [ -z "$owner" ] || by=" (by compose project $owner)"
  warn "port $port is already in use${by}. Starting the lab will fail unless it is freed; pick another with --https-port/--http-port."
}

check_privileged_port() {
  local port=$1
  [ "$port" -lt 1024 ] || return 0
  if docker info --format '{{join .SecurityOptions ","}}' 2>/dev/null | grep -q rootless; then
    warn "rootless Docker cannot publish port $port by default. Use --https-port 8443 --http-port 8080, or allow it with net.ipv4.ip_unprivileged_port_start."
  fi
}

# run_prereq_checks -> 0 if the hard requirements hold.
run_prereq_checks() {
  local rc=0
  check_tools || rc=1
  check_docker || return 1
  check_compose || rc=1
  check_memory
  check_disk "$V3_DIR"
  check_wsl
  return "$rc"
}
