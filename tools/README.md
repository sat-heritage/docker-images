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

## Future audit scripts

Further repository-wide checks belong here as independent, documented tools.
For example, a source-provenance checker comparing the archived source URLs
with official SAT competition distributions could be named
`compare-competition-sources.py`. Such a tool should be read-only by default,
produce a machine-readable report when practical, and clearly document its
network and third-party dependencies.
