#!/bin/sh
set -u
sh outputs/_dr_fan.sh a 2 16
sh outputs/_dr_fan.sh b 2 16
sh outputs/_dr_fan.sh none 2 8 outputs/_dr_ext_cells.txt
echo "ALL FANS DONE $(date +%H:%M:%S)"
