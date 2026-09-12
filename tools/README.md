# Repository tools

This directory contains maintenance and audit utilities that operate on the
repository as a whole. Scripts used inside solver images or during image builds
belong in their corresponding image or builder directory instead.

## Available tools

### `test-all-images.sh`

Tests solver images sequentially and removes each tested image immediately.
The default selection contains every solver marked `ok`; any accepted
`satex list` filter can be supplied. Run it in `tmux` or `screen` for a full
registry test, which can take a long time.

```sh
tools/test-all-images.sh --dry-run
tools/test-all-images.sh '*:2019'
tools/test-all-images.sh --build '*:2019'
tools/test-all-images.sh
```

The command exits with a non-zero status if a solver test fails or an image
cannot be removed. It does not prune shared layers, builder images, or unrelated
Docker data. With `--build`, it compiles each archived source before testing and
removes both the resulting solver image and its builder image. Detailed logs are
stored in `test-results/`, while the console displays only concise status lines
for Docker availability, source download and extraction, build environment,
compilation, image assembly, launch, termination, SAT model, UNSAT result, and
UNSAT proof. Build events are also stored as JSON Lines in
`<solver>-build.jsonl`, so audit tooling can distinguish an unavailable source
from a compiler or Docker image failure without parsing human-oriented logs.

### `validate_metadata.py`

Validates `index.json` and every `solvers.json` and `setup.json` file against
the schemas in `schemas/`.

### `normalize_statuses.py`

Reports legacy solver status strings. Pass `--write` to normalize them while
preserving their original text in `status_detail`.

### `archive_competition_solvers.py`

Downloads one or more official competition ZIP/TAR distributions and creates
one deterministic archive per top-level solver directory. By default, a ZIP
competition distribution produces ZIP assets, preserving the format chosen by
the organizers. Use `--format tar.xz` only when that format is explicitly
wanted. The command is read-only with respect to GitHub unless `--upload` is
supplied. Generated files and a SHA-256 provenance manifest are stored below
the ignored `dist/` directory by default.

To prepare only the first solver being integrated from SAT Competition 2022:

```sh
python3 tools/archive_competition_solvers.py 2022 \
  --archive https://satcompetition.github.io/2022/downloads/sequential-solvers.zip \
  --solver Kissat_MAB-HyWalk
```

Inspect `dist/competition-sources/2022/manifest.json`, then publish the asset to
the `2022-competition` release with a GitHub token having `contents: write`:

```sh
GH_TOKEN=... python3 tools/archive_competition_solvers.py 2022 \
  --archive https://satcompetition.github.io/2022/downloads/sequential-solvers.zip \
  --solver Kissat_MAB-HyWalk \
  --upload
```

On subsequent runs, an identical existing asset is skipped. A differing asset
is never overwritten unless `--replace` is also given. Use repeated `--archive`
options for multiple official track archives, repeated `--solver` options to
select several entries, and `--rename SOURCE=ASSET` when a filesystem-friendly
release asset name is needed.

## Future audit scripts

Further repository-wide checks belong here as independent, documented tools.
For example, a source-provenance checker comparing the archived source URLs
with official SAT competition distributions could be named
`compare-competition-sources.py`. Such a tool should be read-only by default,
produce a machine-readable report when practical, and clearly document its
network and third-party dependencies.
