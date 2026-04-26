#!/usr/bin/env bash
# Build AND push both ART images to Docker Hub.
#
# Usage:
#   ./scripts/azure/release.sh
#   TAG=v1 ./scripts/azure/release.sh
set -euo pipefail

HERE="$(dirname "$0")"

TAG="${TAG:-latest}" \
USERNAME="${DOCKERHUB_USERNAME:-hoso30}" \
DOCKERHUB_USERNAME="${DOCKERHUB_USERNAME:-hoso30}" \
  "${HERE}/build.sh"

TAG="${TAG:-latest}" \
DOCKERHUB_USERNAME="${DOCKERHUB_USERNAME:-hoso30}" \
  "${HERE}/push.sh"

echo ""
echo "Release complete: ${DOCKERHUB_USERNAME:-hoso30}/art-backend:${TAG:-latest}, ${DOCKERHUB_USERNAME:-hoso30}/art-frontend:${TAG:-latest}"
