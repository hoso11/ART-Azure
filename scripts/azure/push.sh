#!/usr/bin/env bash
# Push the two custom ART images to Docker Hub.
# Log in first: docker login
#
# Usage:
#   ./scripts/azure/push.sh
#   TAG=v1 ./scripts/azure/push.sh
set -euo pipefail

TAG="${TAG:-latest}"
USERNAME="${DOCKERHUB_USERNAME:-hoso30}"

BACKEND="${USERNAME}/art-backend:${TAG}"
FRONTEND="${USERNAME}/art-frontend:${TAG}"

echo ""
echo "== Push ${BACKEND} =="
docker push "${BACKEND}"

echo ""
echo "== Push ${FRONTEND} =="
docker push "${FRONTEND}"

echo ""
echo "Pushed to Docker Hub:"
echo "  https://hub.docker.com/r/${USERNAME}/art-backend/tags"
echo "  https://hub.docker.com/r/${USERNAME}/art-frontend/tags"
