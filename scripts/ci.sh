#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python_bin="${NOVA_CI_PYTHON:-python3}"
npm ci --ignore-scripts --no-audit --no-fund
npm run build:avatar
npm run build:talkinghead
npm run build:v2
npm test
node --test .github/scripts/ai-review.test.cjs
for test_name in test_routing.py test_discovery.py test_apple_episode.py; do
  "$python_bin" -m unittest discover -s integrations/catalog -p "$test_name" -v
done
"$python_bin" -m unittest discover -s integrations/kodi -p test_pov.py -v
"$python_bin" -m unittest discover -s tools/avatar -p 'test_*.py' -v
