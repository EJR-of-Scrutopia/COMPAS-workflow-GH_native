#!/usr/bin/env bash
# Fetch the COMPAS project's own example files.
#
# The published wheels do not ship docs or examples, so the upstream
# repositories are cloned shallow into upstream/. Nothing there is edited;
# demo/07_compas_official.py runs those files as they are.
set -euo pipefail

# Anchor to the bench directory so upstream/ lands beside demo/ no
# matter where the caller runs this from.
cd "$(dirname "$0")/.."
mkdir -p upstream
cd upstream
for repo in \
    compas-dev/compas_fab \
    compas-dev/compas_viewer \
    compas-dev/compas_robots \
    BlockResearchGroup/compas_dem
do
    name="$(basename "${repo}")"
    if [ -d "${name}" ]; then
        echo "already present: ${name}"
        continue
    fi
    echo "cloning ${repo}"
    git clone --depth 1 --quiet "https://github.com/${repo}.git" "${name}"
done
echo "Done. List the examples with: python bench/demo/07_compas_official.py"
