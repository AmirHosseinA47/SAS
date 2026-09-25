outputs/_cl_part1_evidence/ - every scratch script (and small output) behind a number in
outputs/carryleg_part1.txt, copied 2026-09-25 from this session's disposable Temp scratchpad
(C:/Users/ahrar/AppData/Local/Temp/claude/E--Projects-SAS/816a1cd9-.../scratchpad/<subdir>),
same subpaths. The verification and review reports (_cl_part1_verify.txt, _cl_part1_review.txt)
cite these by their scratchpad paths. They are read-only analyses of recorded outputs/_ffr_*.json;
several hard-code absolute paths and were run from their scratch dirs, so treat them as evidence,
not as maintained tooling. Excluded: *.pkl (defect1-census/d1_legs.pkl, 1.4 MB, regenerable by
d1.py). This README is not listed in SHA256SUMS.txt.

LINE ENDINGS: the sha256 values in SHA256SUMS.txt are of the bytes as written on 2026-09-25.
This repo has core.autocrlf=true: git stores these text files with LF in the index and may
check them out with CRLF, which changes their hash. To verify after a checkout, hash the
LF form (git show <commit>:<path> | sha256sum, for files that were LF when hashed), or
normalise CRLF->LF before hashing.
