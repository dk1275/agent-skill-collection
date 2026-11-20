---
name: knowledge-base-sync
description: Maintain bidirectional synchronization between the local Obsidian knowledge base and its private GitHub repository on macOS.
metadata:
  short-description: Sync the knowledge base with private GitHub
---

# Knowledge Base Sync

The local knowledge base is `<your-knowledge-base>` (override with KB_SYNC_REPO). Private remotes: origin = <your-private-github-remote>, gitee = <your-private-gitee-remote>. Fetch both before merging origin/main and gitee/main, then push both. Preserve published history using merge; never rebase shared commits. Conflicts pause mutation until resolved. Other devices require their own checkout, credentials and running service; this machine cannot synchronize while sleeping/offline.

Use the installed macOS LaunchAgent and helper script for ordinary operation. The sync loop watches both directions: local edits are committed and pushed after a short debounce; remote commits are fetched and rebased into the local checkout. It must never force-push, reset, discard local edits, or overwrite conflict files.

When a rebase conflict, authentication failure, or remote-history mismatch occurs, stop automatic mutation, report the exact status/log path, and require manual resolution before resuming. Do not include credentials in logs, commits, or skill files.

Useful checks:

```sh
<installed-skill-path>/knowledge-base-sync/scripts/kb-sync.sh --once
<installed-skill-path>/knowledge-base-sync/scripts/kb-sync.sh --status
launchctl print gui/$(id -u)/com.example.knowledge-base-sync
```

The local checkout remains the source of truth for conflict resolution; after resolving a conflict, run `git add`, `git rebase --continue` (if applicable), and a one-shot sync before re-enabling the loop.
