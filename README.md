# Model Governance MIS (MRM/MIS)

Model inventory, tiering, validation, findings, approvals, documents, imports, governance score and Command Center.
Business specification: [`claude.md`](claude.md) (BRD). Earlier requirements and the HTML prototype: `C_Requirements/_OLD/`.

## Folder structure

| Folder | Contents |
|---|---|
| `A_Codes/` | All code. Sub-folders run in prefix order: `AA_infra` (Docker: PostgreSQL, MinIO, Redis), `AB_backend` (FastAPI), `AC_frontend` (React), `AD_seed` (demo-data generators), `AE_launcher` (start/stop/setup), `AZ_tools` (utilities). Details: [`A_Codes/README.md`](A_Codes/README.md) |
| `A_Codes/_OLD/` | Every earlier version of every changed code file (`<name>_v<N>_<YYYYMMDD>.<ext>`) |
| `B_Inputs/` | All input data: `AA_bootstrap` (policy settings, core users), `AB_sample_data` (Phase-2 samples), `AC_seed` (256-model seed templates + synthetic evidence PDFs), `AD_demo_files` (files with deliberate errors for demos), `_OLD` (earlier versions) |
| `C_Requirements/` | Requirements documents and the original prototype |

## Set up on a new computer (e.g. office laptop)

Prerequisites: **Git**, **Python 3.11+** (developed on 3.14), **Node.js 20+**, access to the pip and npm registries.

```powershell
git clone <repository-url> MRM_Governance
cd MRM_Governance
powershell -ExecutionPolicy Bypass -File "A_Codes\AE_launcher\setup_first_time.ps1"
```

Then double-click **MRM Governance MIS** in `A_Codes\AE_launcher` (stop with **Stop MRM Governance MIS**).
The first start creates a local database and loads the demo data (about 30 s) and opens http://localhost:5173.
Sign in by choosing a user and role (no passwords in development mode).

Not in git (rebuilt per machine): the Python environment (`.venv`), frontend packages (`node_modules`), the local
database and stored document copies (`A_Codes/AB_backend/var`), `.env` files, and the shortcuts.
Note: *Reset to seed* regenerates `B_Inputs/AC_seed` and `B_Inputs/AD_demo_files` for the current date, so git will
show those files as changed after a reset. Commit them or discard with `git checkout -- B_Inputs`.

## Working conventions (for people and for Claude Code)

- Code lives in `A_Codes/`, input data in `B_Inputs/`; top-level folders and scripts carry a letter prefix in
  build/run order (`AA_`, `AB_`, …); files inside app folders keep normal names.
- **Never delete code.** Before editing an existing code file, copy it to `_OLD` with the next version number:
  `bash A_Codes/AZ_tools/snapshot.sh A_Codes <path relative to A_Codes>` (same for `B_Inputs`).
- Do not create files outside the project folder (no desktop shortcuts).
- Business rules follow the BRD in `claude.md`: configuration over code, every write audited, AI never commits
  governance data without human confirmation.

## Tests

```powershell
cd A_Codes\AB_backend
.venv\Scripts\python -m pytest          # 135 tests, SQLite, no Docker needed
```
