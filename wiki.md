# Running `meerdata` on CHPC Lengau

This is a CHPC-specific companion to the main [README.md](README.md), covering
how to actually run `meerdata pull`/`extract`/`check`/`verify` on the Lengau
cluster using the `chpc` site config (`src/meerdata/configs/chpc.yaml`, PBS
scheduler). Read the README first for command-level option reference — this
page is about *where* and *how* to run those commands on this specific
cluster, and why.

For the broader install history/decisions (venv setup, dependency gotchas,
caracal/stimela status) see `CHPC_SETUP.md` in `MOTF-newsetup`.

## Why CHPC needs its own instructions

Two things make Lengau different from the `ilifu` site the tool was written
for:

1. **Lengau uses PBS Pro, not SLURM.** The `chpc` site config sets
   `scheduler: pbs`, which submits `qsub` jobs instead of `sbatch` jobs.
2. **Lengau compute nodes have no internet access.** The `download` step
   (pulling the raw MVF data from the SARAO archive via `mvf_download.py`)
   can never run as a PBS batch job — it always runs in the foreground on
   whichever node you invoke `meerdata pull` from. **You must invoke it from
   `scp.chpc.ac.za`** (CHPC's dedicated data-transfer node — not the shared
   `lengau.chpc.ac.za` login node), inside a **persistent `screen` or `tmux`
   session**, since a download can run for hours and there is no scheduler
   behind it to auto-requeue it if your SSH connection drops.

Everything else (`auto`/`ms`/`cleanup`/`sanity-check`) is submitted to PBS
automatically, in the same `meerdata pull` invocation, once `download`
finishes successfully — you don't run those separately.

## 1. One-time setup

```bash
# Environment (see CHPC_SETUP.md for how this venv was built)
source ~/vnv/vnv_meerdata/bin/activate
meerdata --version   # sanity check: should print "meerdata, version X.Y.Z"
```

Confirm the `chpc` site config is picked up:

```bash
meerdata --site chpc verify -b 0000000000
```

(A nonsense block number is fine here — this just exercises site-config
loading; it should report `[MISSING]`, not raise a config error.)

> **Before running for real:** `src/meerdata/configs/chpc.yaml` still has
> placeholder values — `-P <CHPC_PROJECT_CODE>` (PBS project/account code)
> and `-q normal` (queue name) under `pbs.options`, and `paths.venv` /
> `paths.data_folder` / `paths.sanity_check_folder` are all `null`. Fill
> these in (or pass `--data-folder`/`--venv`/`--sanity-check-folder`
> explicitly on every command) before relying on site defaults.

## 2. Obtaining an RDB link

You need SARAO archive access (ask the PI/project maintainers for
permission if you don't have it — see the main README's
[Obtaining RDB link](README.md#obtaining-rdb-link) section).

1. Log in to the [SARAO archive](https://archive.sarao.ac.za/).
2. Find the block (CBID) you want.
3. Click **".RDB FILE LINK"** (top right of the block view) to copy the link.
   It looks like:
   ```
   https://archive-gw-1.kat.ac.za/1234567890/1234567890_sdp_l0.full.rdb?token=abc123...
   ```
   The numeric prefix (`1234567890`) is the CBID; the `token=` query
   parameter is a time-limited access token — treat the whole link as a
   secret and don't paste it into shared logs/chat.

## 3. Running the download (on `scp.chpc.ac.za`, in `screen`)

From `lengau.chpc.ac.za` (or your own machine), SSH to the data-transfer
node, not the shared login node:

```bash
ssh scp.chpc.ac.za
```

Start (or reattach to) a persistent `screen` session — this is what protects
the download from an SSH drop:

```bash
screen -S meerdata-pull        # first time
# or, if you already started one earlier:
screen -r meerdata-pull        # reattach
```

Inside the `screen` session:

```bash
source ~/vnv/vnv_meerdata/bin/activate

meerdata --site chpc pull \
  -r "https://archive-gw-1.kat.ac.za/1234567890/1234567890_sdp_l0.full.rdb?token=abc123..." \
  -c all
```

`-c all` pulls both autocorrelations (`auto`) and the cross-correlation
measurement set (`ms`); use `-c auto` or `-c cross` if you only need one.
Add `--data-folder`/`--venv` explicitly if you haven't filled in
`chpc.yaml`'s site defaults yet.

What happens next, all within this one command:

1. `download` runs immediately, in the foreground, in this `screen` session
   — this is the actual `mvf_download.py` pull from the archive, and can
   take a long time depending on block size and archive load.
2. Detach whenever you like (`Ctrl-A` then `D`) — the download keeps running
   in the background on `scp.chpc.ac.za`. Reattach later with
   `screen -r meerdata-pull` to check progress or see it finish.
3. **The moment `download` exits successfully**, the same process
   automatically builds and submits `auto`/`ms`/`cleanup` (whichever you
   requested) as PBS jobs via `qsub`, printing their job IDs. `cleanup`
   is submitted with a `-W depend=afterok:...` dependency on the
   extraction jobs, so it only runs after they succeed.
4. If `download` fails, nothing gets submitted to PBS — fix whatever broke
   (usually a network hiccup or an expired token) and re-run.

You can safely log out of `scp.chpc.ac.za` entirely once the PBS jobs are
submitted (step 3) — they're now tracked by PBS, independent of your
session.

## 4. Checking on PBS jobs

From the login node (`lengau.chpc.ac.za`):

```bash
qstat -u $USER              # your jobs and their state (Q/R/H/E)
qstat -f <jobid>             # full detail on one job
```

Logs land in `./logs/` (relative to wherever you ran `meerdata pull` from —
i.e. on `scp.chpc.ac.za`, in the directory you were in inside the `screen`
session), named after each job's PBS job name/ID. Generated `.pbs` scripts
themselves are written to `./sbatch/` (yes, that directory name is shared
with the SLURM path in this tool — harmless, just a naming leftover) for
inspection or manual re-submission.

## 5. Sanity check and verify

`check` (the museek sanity-check pipeline) and `verify` (disk-usage/existence
check) both work the same way as on other sites — `check` submits its one
step to PBS as usual (no special-casing, since it isn't a download), `verify`
never touches a scheduler at all:

```bash
meerdata --site chpc check -r "RDB_LINK"
meerdata --site chpc verify -b 1234567890 -b 1234567891
```

## 6. `extract` — processing an RDB you already have locally

If you already have an RDB file on disk (e.g. from a previous `pull`, or
copied in some other way) and just want to (re-)run extraction, `extract`
never touches `download` at all, so it can be run directly from the login
node — no `screen`/`scp.chpc.ac.za` dance needed:

```bash
meerdata --site chpc extract -r /path/to/1234567890_sdp_l0.full.rdb -c all
```

## Troubleshooting

* **`meerdata --site chpc ...` complains about an unknown site** — you're
  likely running an older install; make sure `~/vnv/vnv_meerdata` has the
  `chpc` branch's version of `meerdata` installed (`pip show meerdata` should
  show a version string containing a recent git commit, e.g.
  `2.0.1.dev0+g82b32cc...`), not the plain `main`-branch install.
* **PBS jobs stay `Q` (queued) for a long time** — check `-P`/`-q` in
  `chpc.yaml` are real, valid values for your account; a bad project code
  or queue name won't error at submission time on some PBS setups, it just
  never schedules.
* **`screen` session vanished / download seems to have died** — `screen -ls`
  on `scp.chpc.ac.za` to list sessions; if it's genuinely gone (not just
  detached), the download did not survive and needs restarting — this is
  exactly the failure mode the `screen` session exists to prevent, so if it
  keeps happening check whether `scp.chpc.ac.za` itself is stable for you,
  and consider `tmux` instead if you find it more reliable.
* **General pip/dependency install issues on this cluster** (git config
  bugs, numpy build failures, "no wheel for latest version") — see
  `CHPC_SETUP.md`'s "CHPC Python env gotchas" section; none of that is
  specific to `meerdata` usage, only to installing/upgrading it.

## Known gaps (as of 2026-09-14)

* `chpc.yaml`'s PBS project code, queue, and site paths are still
  placeholders — see "1. One-time setup" above.
* This has been tested via dry-run and unit tests, but **not yet against a
  real block end-to-end** on Lengau's actual PBS Pro 18.2.1 scheduler.
* No CHPC-specific guidance exists on wiki.chpc.ac.za for MeerKAT/SARAO data
  — the `scp.chpc.ac.za` recommendation here comes from CHPC's general
  data-transfer-node documentation, not anything astronomy-specific.
