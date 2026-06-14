#!/usr/bin/env bash
set -euo pipefail

echo "===== Task 3 Mock Verification: Multi-camera synchronization ====="
date -Iseconds

mkdir -p data

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
import openarm_dataset

dataset = openarm_dataset.Dataset("data/openarm_mock_dataset")

print("num_episodes:", dataset.num_episodes)
print("camera_names:", dataset.camera_names)
print("metadata episodes:", dataset.meta.episodes)
print("metadata tasks:", dataset.meta.tasks)

cameras = dataset.load_cameras(0)
print("loaded cameras:", sorted(cameras.keys()))

for name, camera in sorted(cameras.items()):
    print(name, "num_frames=", camera.num_frames)
    timestamps = camera.load_timestamps()
    print(name, "first_timestamp=", timestamps[0], "last_timestamp=", timestamps[-1])

samples = dataset.sample(hz=30, episode_index=0)
print("num_samples:", len(samples))

if len(samples) == 0:
    raise RuntimeError("Expected at least one synchronized sample")

sample = samples[0]
print("sample timestamp:", sample.timestamp)
print("sample obs keys:", sorted(sample.obs.keys()))
print("sample camera keys:", sorted(sample.cameras.keys()))

expected_cameras = {"wrist_left", "wrist_right", "ceiling", "head"}
if set(sample.cameras.keys()) != expected_cameras:
    raise RuntimeError(f"Unexpected cameras: {sample.cameras.keys()}")

print("Task 3 OpenArm Dataset API verification passed.")
PY

echo
echo "===== Task 3 mock verification completed ====="