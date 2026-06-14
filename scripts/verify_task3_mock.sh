#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "===== Task 3 Mock Verification: Multi-camera synchronization ====="
date -Iseconds

mkdir -p data artifacts

echo
echo "===== Run Task 2 mock to generate joint states ====="
./scripts/verify_task2_mock.sh

echo
echo "===== Generate OpenArm Dataset-style camera episode ====="
python3 scripts/simulate_cams.py \
  --joint-states data/joint_states_mock.jsonl \
  --output-root data/openarm_mock_dataset \
  --episode-id 0 \
  --overwrite

echo
echo "===== Inspect generated dataset tree ====="
find data/openarm_mock_dataset -maxdepth 4 -type d | sort
find data/openarm_mock_dataset/episodes/0/cameras -type f | head -n 12

echo
echo "===== Verify with openarm_dataset API ====="
python3 - <<'PY'
from pathlib import Path

import openarm_dataset

DATASET_ROOT = Path("data/openarm_mock_dataset")
EXPECTED_CAMERAS = {"wrist_left", "wrist_right", "ceiling", "head"}
EPISODE = {"id": "0"}

dataset = openarm_dataset.Dataset(str(DATASET_ROOT))

print("num_episodes:", dataset.num_episodes)
print("camera_names:", dataset.camera_names)

if hasattr(dataset, "meta"):
    print("metadata episodes:", getattr(dataset.meta, "episodes", None))
    print("metadata tasks:", getattr(dataset.meta, "tasks", None))

if dataset.num_episodes < 1:
    raise RuntimeError("Expected at least one episode")

cameras = dataset.load_cameras(EPISODE)

print("loaded camera keys:", sorted(cameras.keys()))

if set(cameras.keys()) != EXPECTED_CAMERAS:
    raise RuntimeError(f"Unexpected cameras: {cameras.keys()}")

for camera_name, camera in cameras.items():
    timestamps = camera.load_timestamps()
    print(camera_name, "num_frames:", len(timestamps))

    if len(timestamps) == 0:
        raise RuntimeError(f"{camera_name} has no frames")

    if timestamps != sorted(timestamps):
        raise RuntimeError(f"{camera_name} timestamps are not sorted")

print("Camera loading and timestamp verification passed.")

left_state = DATASET_ROOT / "episodes" / "0" / "obs" / "arms" / "left" / "state.parquet"
right_state = DATASET_ROOT / "episodes" / "0" / "obs" / "arms" / "right" / "state.parquet"

if not left_state.exists():
    raise RuntimeError(f"Missing left arm state parquet: {left_state}")

if not right_state.exists():
    raise RuntimeError(f"Missing right arm state parquet: {right_state}")

print("left_state:", left_state)
print("right_state:", right_state)
print("Joint state parquet verification passed.")

print("Task 3 OpenArm Dataset API verification passed.")
PY

if [ "${KEEP_GENERATED_DATA:-0}" != "1" ]; then
  echo
  echo "===== Cleanup Task 3 generated dataset ====="
  rm -rf data/openarm_mock_dataset
  rm -f data/joint_states_mock.jsonl
else
  echo
  echo "KEEP_GENERATED_DATA=1, keeping generated dataset."
fi

echo
echo "===== Task 3 mock verification completed ====="