# Environment — training-free / ABHE-v0

## Host
- SSH alias: `10.220.5.159`
- User: `root`
- Hostname: `qiuyn0-0`
- Port: 30412 (note: a second SSH config exists for the same IP on port 31256 — ensure the right entry is used)

## Project root
```
/cephfs/qiuyn/training-free
```

## Python
- venv path: `.venv/`
- Activate convention: run with `PYTHONPATH=.:src .venv/bin/python` (no `activate`)

Example:
```bash
cd /cephfs/qiuyn/training-free
PYTHONPATH=.:src .venv/bin/python scripts/check_abhe_no_leakage_boundary.py --compact --strict
```

## Git
- Remote: `https://github.com/CherryQqqqq5/training-free` (private)
- Live remote branch (as of 2026-05-19): `cleanup/repo-tidy-pre-p1` @ `e0a6e87`
- Intended sprint branch: `stage1-bfcl-performance-sprint` @ `badc821`

## How to log in
```bash
ssh -t 10.220.5.159 'cd /cephfs/qiuyn/training-free && exec $SHELL -l'
```

## Known env issues
- Two SSH configs on the same IP → if `ssh` lands on the wrong one, port mismatch will fail silently. Verify with `ssh <host> hostname`.
- All runners assume `PYTHONPATH=.:src` — running without it gives import errors.
