#!/bin/bash
set -u

REPO="${KB_SYNC_REPO:-<your-knowledge-base>}"
REMOTE="origin"
BRANCH="main"
STATE_DIR="${HOME}/Library/Application Support/knowledge-base-sync"
LOG_FILE="${STATE_DIR}/sync.log"
LOCK_DIR="${STATE_DIR}/.lock"
DEBOUNCE_SECONDS=8

mkdir -p "$STATE_DIR"
exec >>"$LOG_FILE" 2>&1

log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S%z')" "$*"; }

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  log "another sync run is active; exiting"
  exit 0
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT
trap 'exit 0' TERM INT

cd "$REPO" || { log "repository unavailable: $REPO"; exit 1; }

status() {
  printf 'repo=%s\nbranch=%s\nremote=%s\n' "$REPO" "$BRANCH" "$REMOTE"
  git status --short --branch
  git log -1 --oneline
}

sync_once() {
  if [ "$(git branch --show-current)" != "$BRANCH" ]; then
    log "paused: expected main branch"
    return 2
  fi
  if [ -d .git/rebase-merge ] || [ -d .git/rebase-apply ] || [ -f .git/MERGE_HEAD ]; then
    log "paused: unfinished merge or rebase requires manual resolution"
    return 2
  fi

  if [ -n "$(git status --porcelain)" ]; then
    sleep "$DEBOUNCE_SECONDS"
    if [ -n "$(git status --porcelain)" ]; then
      git add -A || return 1
      git commit -m "Sync knowledge base changes" || {
        log "local commit failed"
        return 1
      }
      log "committed local changes"
    fi
  fi

  if ! git -c "http.https://github.com.proxy=" fetch "$REMOTE" "$BRANCH" || ! git fetch gitee "$BRANCH"; then
    log "fetch failed; will retry"
    return 1
  fi

  if ! git merge --no-edit "origin/$BRANCH" || ! git merge --no-edit "gitee/$BRANCH"; then
    log "paused: rebase conflict or pull failure; resolve manually"
    return 2
  fi

  if ! git -c "http.https://github.com.proxy=" push "$REMOTE" "$BRANCH" || ! git push gitee "$BRANCH"; then
    log "push failed; will retry"
    return 1
  fi
  log "sync complete"
  return 0
}

case "${1:---loop}" in
  --status) status; exit 0 ;;
  --once) sync_once; exit $? ;;
  --loop)
    while true; do
      sync_once || true
      sleep 30
    done
    ;;
  *) echo "usage: $0 [--once|--status|--loop]" >&2; exit 2 ;;
esac
