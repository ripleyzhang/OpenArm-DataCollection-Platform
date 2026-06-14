#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

export PYTHONPATH="$REPO_ROOT/src:$PYTHONPATH"
export OPENARM_DATASET_ROOT="$REPO_ROOT/data/openarm_mock_dataset"

ARTIFACT_DIR="$REPO_ROOT/artifacts"
DATASET_ROOT="$REPO_ROOT/data/openarm_mock_dataset"
DOWNLOADED_ZIP="$REPO_ROOT/data/episode_0_downloaded.zip"

mkdir -p "$ARTIFACT_DIR"

cleanup_generated_dataset() {
  echo
  echo "===== Cleanup generated dataset ====="

  if [ -d "$DATASET_ROOT" ]; then
    rm -rf "$DATASET_ROOT"
    echo "Removed $DATASET_ROOT"
  fi

  if [ -f "$REPO_ROOT/data/joint_states_mock.jsonl" ]; then
    rm -f "$REPO_ROOT/data/joint_states_mock.jsonl"
    echo "Removed data/joint_states_mock.jsonl"
  fi

  echo "Kept artifacts under $ARTIFACT_DIR"
}

echo "===== Task 4 Mock Verification: Storage Backend + REST API ====="
date -Iseconds

echo
echo "===== Ensure Task 3 dataset exists ====="
if [ ! -f "$DATASET_ROOT/metadata.yaml" ]; then
  echo "Task 3 dataset not found. Running Task 3 verification first..."
  ./scripts/verify_task3_mock.sh
fi

echo
echo "===== Verify storage layer directly ====="
python3 - <<'PY'
from pathlib import Path
import json

from storage import (
    get_episode_metadata,
    list_episode_ids,
    load_dataset_metadata,
    create_episode_zip,
)

root = Path("data/openarm_mock_dataset")
artifact_dir = Path("artifacts")
artifact_dir.mkdir(exist_ok=True)

metadata = load_dataset_metadata(root)
print("dataset_version:", metadata.get("version"))

episode_ids = list_episode_ids(root)
print("episode_ids:", episode_ids)

if "0" not in episode_ids:
    raise RuntimeError("Expected episode 0")

episode_meta = get_episode_metadata(root, "0")
print("episode_metadata:", episode_meta)

with (artifact_dir / "episode_0_metadata.json").open("w", encoding="utf-8") as f:
    json.dump(episode_meta, f, indent=2)

zip_path = create_episode_zip(root, "0", artifact_dir)
print("zip_path:", zip_path)
print("zip_size_bytes:", zip_path.stat().st_size)

if zip_path.stat().st_size <= 0:
    raise RuntimeError("Episode zip is empty")
PY

echo
echo "===== Start API server ====="
uvicorn api:app --host 127.0.0.1 --port 8000 &
API_PID=$!

stop_api() {
  echo
  echo "===== Stop API server ====="
  if kill -0 "$API_PID" >/dev/null 2>&1; then
    kill "$API_PID" || true
    wait "$API_PID" || true
  fi
}

trap 'stop_api; cleanup_generated_dataset' EXIT

sleep 2

echo
echo "===== Test API endpoints ====="

curl -f http://127.0.0.1:8000/health | tee "$ARTIFACT_DIR/api_health.json"
echo

curl -f http://127.0.0.1:8000/episodes | tee "$ARTIFACT_DIR/api_episodes.json"
echo

curl -f http://127.0.0.1:8000/episodes/0/metadata | tee "$ARTIFACT_DIR/api_episode_0_metadata.json"
echo

curl -f -L http://127.0.0.1:8000/episodes/0/download -o "$ARTIFACT_DIR/episode_0_from_api.zip"

echo
echo "===== Verify downloaded zip ====="
ls -lh "$ARTIFACT_DIR/episode_0.zip"
ls -lh "$ARTIFACT_DIR/episode_0_from_api.zip"

if [ ! -s "$ARTIFACT_DIR/episode_0_from_api.zip" ]; then
  echo "ERROR: downloaded zip is missing or empty"
  exit 1
fi

echo
echo "===== Task 4 mock verification completed ====="