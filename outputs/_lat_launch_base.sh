#!/usr/bin/env bash
# Lateral round: baseline wave against a detached dd0a1b9 worktree, with the
# extended harness (direct hold hook + burn intervals). One 13-run wave.
cd /e/Projects/SAS || exit 1
bash outputs/_ffr_runall.sh latbase "C:/Users/ahrar/AppData/Local/Temp/claude/E--Projects-SAS/046c0599-73e6-46e0-90db-45436bf5dbad/scratchpad/basedd0a1b9" > outputs/_ffr_runall_latbase.log 2>&1
