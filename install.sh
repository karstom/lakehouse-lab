#!/usr/bin/env bash
# Lakehouse Lab one-line installer (bootstrap).
#
#   curl -fsSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash
#   curl -fsSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash -s -- --profile engineer
#
# It only fetches the repository and hands over to v3/install.sh, which does the real work:
#   1. clone the repository at --ref (default: main) into --dir (default: ./lakehouse-lab),
#      or update an existing, clean Lakehouse Lab V3 checkout there;
#   2. exec v3/install.sh with every option this script does not know.
# It prints what it will do before doing it. Everything is inside main(), called on the
# last line, so a partial download runs nothing.
#
# It refuses to touch a directory that is not a git checkout of Lakehouse Lab V3, including
# a V2 install (see docs/MIGRATION.md and legacy/README.md).

main() {
  set -euo pipefail

  local default_repo="https://github.com/karstom/lakehouse-lab.git"
  local repo="${LAKEHOUSE_REPO:-$default_repo}"
  local ref="${LAKEHOUSE_REF:-main}"
  local dir="${LAKEHOUSE_DIR:-}"
  local assume_yes=0 dir_given=0 ref_given=0
  [ -n "${LAKEHOUSE_DIR:-}" ] && dir_given=1
  [ -n "${LAKEHOUSE_REF:-}" ] && ref_given=1
  local -a pass=()

  local c_bold="" c_red="" c_yellow="" c_reset=""
  if [ -t 2 ]; then
    c_bold=$'\033[1m' c_red=$'\033[31m' c_yellow=$'\033[33m' c_reset=$'\033[0m'
  fi
  say() { printf '%s\n' "$*" >&2; }
  warn() { printf '%sWARNING:%s %s\n' "$c_yellow" "$c_reset" "$*" >&2; }
  die() { printf '%sERROR:%s %s\n' "$c_red" "$c_reset" "$*" >&2; exit 1; }
  need_value() { [ $# -ge 2 ] && [ -n "$2" ] || die "$1 needs a value"; }

  usage() {
    cat >&2 <<EOF
Lakehouse Lab one-line installer: fetches the repository, then runs v3/install.sh.

Usage: install.sh [bootstrap options] [v3/install.sh options]
       curl -fsSL <url>/install.sh | bash -s -- [options]

Bootstrap options (environment variable in brackets):
  --ref REF      branch or tag to install (default: main)            [LAKEHOUSE_REF]
  --dir DIR      where the repository goes (default: ./lakehouse-lab) [LAKEHOUSE_DIR]
  --repo URL     repository to clone (default: $default_repo) [LAKEHOUSE_REPO]
  --yes          do not ask for confirmation (implied by --non-interactive)
  -h, --help     this help; 'install.sh -- --help' shows v3/install.sh's options
  --             pass everything after it to v3/install.sh unchanged

Every other option goes to v3/install.sh, e.g. --profile engineer, --domain sslip,
--non-interactive. An existing checkout in DIR is updated (fast-forward only) if it has no
uncommitted changes; any other existing, non-empty directory is left alone.
EOF
  }

  while [ $# -gt 0 ]; do
    case "$1" in
      --ref) need_value "$@"; ref=$2; ref_given=1; shift ;;
      --ref=*) ref=${1#*=}; ref_given=1 ;;
      --dir) need_value "$@"; dir=$2; dir_given=1; shift ;;
      --dir=*) dir=${1#*=}; dir_given=1 ;;
      --repo) need_value "$@"; repo=$2; shift ;;
      --repo=*) repo=${1#*=} ;;
      --yes|-y) assume_yes=1 ;;
      -h|--help) usage; return 0 ;;
      --) shift; pass+=("$@"); break ;;
      --non-interactive) assume_yes=1; pass+=("$1") ;;
      *) pass+=("$1") ;;
    esac
    shift
  done

  [ -n "$ref" ] || die "--ref needs a value"
  [ -n "$repo" ] || die "--repo needs a value"
  # A ref is a branch or tag name; refuse anything git would read as an option or a range.
  if ! [[ "$ref" =~ ^[A-Za-z0-9._/-]+$ ]] || [[ "$ref" == -* ]] || [[ "$ref" == *..* ]]; then
    die "--ref: '$ref' is not a branch or tag name"
  fi
  [[ "$repo" == -* ]] && die "--repo: '$repo' is not a repository URL"
  command -v git >/dev/null 2>&1 || die "git is required (e.g. 'sudo apt-get install git'), then run this again."

  # is_v3_checkout DIR: a git work tree (top level) that contains the V3 installer.
  is_v3_checkout() {
    [ -f "$1/v3/install.sh" ] && [ -f "$1/v3/lab" ] || return 1
    local top
    top=$(git -C "$1" rev-parse --show-toplevel 2>/dev/null) || return 1
    [ "$(cd -P "$top" && pwd)" = "$(cd -P "$1" && pwd)" ]
  }
  # is_v2_install DIR: a Lakehouse Lab V2 install (V2 compose file at the top, no v3/).
  is_v2_install() {
    [ ! -d "$1/v3" ] && { [ -f "$1/docker-compose.yml" ] || [ -f "$1/start-lakehouse.sh" ]; }
  }
  refuse_v2() {
    die "$1 looks like a Lakehouse Lab V2 install. This installer will not change it:
  updating it would replace V2's files with V3 while V2 is still using them.
  - To install V3 next to it:   add --dir <another directory>, e.g. --dir ~/lakehouse-lab-v3
  - To keep V2 as it is:        cd $1 && git fetch --tags && git checkout v2.1.1-final
  - Moving your data to V3:     https://github.com/karstom/lakehouse-lab/blob/main/docs/MIGRATION.md"
  }

  # Run from inside a checkout (./install.sh) with no --dir/--ref: use that checkout as is.
  local self="${BASH_SOURCE[0]:-}" self_dir=""
  if [ -n "$self" ] && [ -f "$self" ]; then
    self_dir=$(cd -P "$(dirname "$self")" && pwd)
  fi
  if [ -n "$self_dir" ] && [ "$dir_given" = 0 ] && [ "$ref_given" = 0 ] && is_v3_checkout "$self_dir"; then
    say "${c_bold}Lakehouse Lab${c_reset}: using this checkout ($self_dir)."
    say "Running: v3/install.sh $(show_args "${pass[@]+"${pass[@]}"}")"
    exec bash "$self_dir/v3/install.sh" "${pass[@]+"${pass[@]}"}"
  fi

  if [ "$dir_given" = 0 ]; then
    # Inside a checkout already (e.g. 'curl … | bash' from its top level): use it rather
    # than nesting a second clone below it.
    if is_v3_checkout "$PWD"; then
      dir=$PWD
    elif is_v2_install "$PWD" && git -C "$PWD" rev-parse --git-dir >/dev/null 2>&1; then
      refuse_v2 "$PWD"
    else
      dir="$PWD/lakehouse-lab"
    fi
  fi
  # A literal '~' (e.g. from LAKEHOUSE_DIR='~/lab') means the home directory.
  local tilde='~'
  if [ "$dir" = "$tilde" ]; then
    dir=$HOME
  elif [ "${dir:0:2}" = "$tilde/" ]; then
    dir="$HOME/${dir:2}"
  fi
  case "$dir" in /*) ;; *) dir="$PWD/$dir" ;; esac

  # Decide what to do with the target directory before doing anything.
  local action
  if [ ! -e "$dir" ]; then
    action=clone
  elif [ ! -d "$dir" ]; then
    die "$dir exists and is not a directory. Choose another place with --dir."
  elif [ -z "$(ls -A "$dir" 2>/dev/null)" ]; then
    action=clone
  elif is_v3_checkout "$dir"; then
    action=update
  elif is_v2_install "$dir"; then
    refuse_v2 "$dir"
  else
    die "$dir exists, is not empty, and is not a Lakehouse Lab V3 checkout. Nothing was changed.
  Choose an empty or new directory with --dir, or move that one out of the way."
  fi

  if [ "$action" = update ]; then
    local origin
    origin=$(git -C "$dir" remote get-url origin 2>/dev/null || true)
    [ -n "$origin" ] || die "$dir is a git checkout with no 'origin' remote; update it yourself, or use another --dir."
    if [ "$(normalize_url "$origin")" != "$(normalize_url "$repo")" ]; then
      die "$dir is a checkout of $origin, not $repo. Pass --repo $origin to use it, or choose another --dir."
    fi
    if [ -n "$(git -C "$dir" status --porcelain --untracked-files=no 2>/dev/null)" ]; then
      die "$dir has uncommitted changes to tracked files ('git -C $dir status'). Commit or stash them first; nothing was changed."
    fi
  fi

  say ""
  say "${c_bold}Lakehouse Lab installer${c_reset}"
  say "  repository : $repo"
  say "  ref        : $ref"
  say "  directory  : $dir"
  if [ "$action" = clone ]; then
    say "  step 1     : git clone --branch $ref $repo $dir"
  else
    say "  step 1     : update the existing checkout to $ref (fast-forward only; your settings,"
    say "               secrets and data are untracked and stay as they are)"
  fi
  say "  step 2     : $dir/v3/install.sh $(show_args "${pass[@]+"${pass[@]}"}")"
  say "               (checks Docker, writes v3/.env and v3/.secrets.env, starts the lab)"
  say ""

  # stdin is the script itself when piped to bash, so ask (and let v3/install.sh ask) on
  # the terminal. With no terminal, run without questions.
  local tty=""
  if [ -t 0 ]; then
    tty=/dev/stdin
  elif { : </dev/tty; } 2>/dev/null; then
    tty=/dev/tty
  fi
  if [ "$assume_yes" = 0 ] && [ -n "$tty" ]; then
    local answer=""
    printf 'Continue? [Y/n] ' >&2
    read -r answer <"$tty" || answer=n
    case "$answer" in
      ""|[Yy]|[Yy][Ee][Ss]) ;;
      *) say "Stopped; nothing was changed."; return 1 ;;
    esac
  fi

  if [ "$action" = clone ]; then
    git clone --branch "$ref" -- "$repo" "$dir" \
      || die "could not clone $repo at '$ref' (is the ref a branch or tag that exists?)"
  else
    update_checkout "$dir" "$ref"
  fi

  [ -f "$dir/v3/install.sh" ] || die "$ref has no v3/install.sh; it is not a Lakehouse Lab V3 ref."
  say ""
  say "Running v3/install.sh $(show_args "${pass[@]+"${pass[@]}"}")"
  if [ -n "$tty" ] && [ ! -t 0 ]; then
    exec bash "$dir/v3/install.sh" "${pass[@]+"${pass[@]}"}" <"$tty"
  fi
  exec bash "$dir/v3/install.sh" "${pass[@]+"${pass[@]}"}"
}

# show_args ARGS... -> the arguments for display, with secret values replaced by '***'.
show_args() {
  local out="" hide=0 a
  for a in "$@"; do
    if [ "$hide" = 1 ]; then a='***'; hide=0
    else
      case "$a" in
        --*secret*=*|--*password*=*|--*token*=*) a="${a%%=*}=***" ;;
        --*secret*|--*password*|--*token*) hide=1 ;;
      esac
    fi
    out+="${out:+ }$a"
  done
  printf '%s' "$out"
}

# normalize_url URL -> a comparable form (scheme, user, trailing '/' and '.git' removed).
normalize_url() {
  local u=$1
  u=${u%/}
  u=${u%.git}
  u=${u#*://}
  u=${u#*@}
  u=${u/://}
  printf '%s\n' "$u"
}

# update_checkout DIR REF: fetch REF from origin and move to it without losing local work.
# A branch is fast-forwarded (never reset); a tag is checked out detached.
update_checkout() {
  local dir=$1 ref=$2 current
  git -C "$dir" fetch --tags origin || die "git fetch failed in $dir"
  local target=""
  if git -C "$dir" rev-parse -q --verify "refs/remotes/origin/$ref" >/dev/null; then
    target="refs/remotes/origin/$ref"
  elif git -C "$dir" rev-parse -q --verify "refs/tags/$ref" >/dev/null; then
    target="refs/tags/$ref"
  else
    die "'$ref' is not a branch or tag of $(git -C "$dir" remote get-url origin)"
  fi
  # Never switch a V3 checkout to a ref without V3 (e.g. a V2 tag): nothing is changed.
  git -C "$dir" cat-file -e "$target:v3/install.sh" 2>/dev/null \
    || die "$ref has no v3/install.sh; it is not a Lakehouse Lab V3 ref. Nothing was changed."
  if [ "$target" = "refs/remotes/origin/$ref" ]; then
    current=$(git -C "$dir" symbolic-ref -q --short HEAD || true)
    if [ "$current" != "$ref" ]; then
      if git -C "$dir" rev-parse -q --verify "refs/heads/$ref" >/dev/null; then
        git -C "$dir" checkout -q "$ref" || die "could not switch $dir to branch $ref"
      else
        git -C "$dir" checkout -q -b "$ref" --track "origin/$ref" || die "could not create branch $ref in $dir"
        return 0
      fi
    fi
    git -C "$dir" merge -q --ff-only "origin/$ref" \
      || die "branch $ref in $dir has commits that are not on origin/$ref; update it yourself (nothing was changed)."
  else
    git -C "$dir" checkout -q --detach "$target" || die "could not check out tag $ref in $dir"
  fi
}

main "$@"
