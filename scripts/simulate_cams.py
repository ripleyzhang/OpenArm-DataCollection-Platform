#!/usr/bin/env python3
"""
Task 3 mock: simulate synchronized camera frames and write an OpenArm Dataset-style episode.

Inputs:
- data/joint_states_mock.jsonl from Task 2

Outputs:
- data/openarm_mock_dataset/metadata.yaml
- data/openarm_mock_dataset/episodes/0/obs/arms/left/state.parquet
- data/openarm_mock_dataset/episodes/0/obs/arms/right/state.parquet
- data/openarm_mock_dataset/episodes/0/action/arms/left/qpos.parquet
- data/openarm_mock_dataset/episodes/0/action/arms/right/qpos.parquet
- data/openarm_mock_dataset/episodes/0/cameras/{wrist_left,wrist_right,ceiling,head}/*.jpeg

This intentionally mimics the OpenArm Dataset layout:
- camera frame filenames are nanosecond timestamps
- camera streams are stored as JPEG directories
- joint observations are stored under obs/arms/{left,right}/state.parquet
"""

import argparse
import json
import shutil
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
import yaml
from PIL import Image, ImageDraw


JOINT_COLUMNS = [
    "joint1",
    "joint2",
    "joint3",
    "joint4",
    "joint5",
    "joint6",
    "joint7",
    "gripper",
]

# cameras running at different frame rates
CAMERA_FPS = {
    "wrist_left": 30.0,
    "wrist_right": 30.0,
    "ceiling": 15.0,
    "head": 60.0,
}


def load_joint_states(path: Path) -> List[dict]:
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    if not records:
        raise ValueError(f"No joint-state records found in {path}")

    return records


def make_arm_dataframe(records: List[dict], arm_name: str) -> pd.DataFrame:
    """
    Convert per-joint JSONL records into one time-indexed arm state DataFrame.

    Output columns:
    qpos_joint1 ... qpos_gripper
    qvel_joint1 ... qvel_gripper
    qtorque_joint1 ... qtorque_gripper

    The OpenArm Dataset loader expects state.parquet to contain qpos/qvel/qtorque
    arrays for all 8 joints. The exact internal schema may evolve, so this mock
    keeps the data explicit and easy to inspect.
    """
    # filter data with arm name
    arm_records = [r for r in records if r["arm_name"] == arm_name]
    if not arm_records:
        raise ValueError(f"No records found for arm_name={arm_name}")

    # hashtable {timestamp: {joint_name: record_data}}
    by_timestamp: Dict[int, Dict[str, dict]] = {}
    for r in arm_records:
        ts = int(r["sensor_timestamp_ns"])
        joint_name = r["joint_name"]

        if joint_name == "J8_gripper":
            col = "gripper"
        else:
            col = f"joint{int(r['joint_index'])}"

        by_timestamp.setdefault(ts, {})[col] = r

    rows = []

    for ts in sorted(by_timestamp):
        joint_map = by_timestamp[ts]

        # Keep only timestamps where all 8 joints are present.
        if not all(joint in joint_map for joint in JOINT_COLUMNS):
            continue

        row = {"timestamp_ns": ts}

        for joint in JOINT_COLUMNS:
            r = joint_map[joint]
            row[f"qpos_{joint}"] = float(r["position_rad"])
            row[f"qvel_{joint}"] = float(r["velocity_rad_s"])
            row[f"qtorque_{joint}"] = float(r["torque_nm"])

        rows.append(row)

    if not rows:
        raise ValueError(f"No complete 8-joint timesteps found for arm_name={arm_name}")

    # Convert ns integers to the Pandas datetime type and set them as the row index.
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp_ns"], unit="ns", utc=False)
    df = df.drop(columns=["timestamp_ns"]).set_index("timestamp")

    return df.astype("float32")


def make_action_dataframe(obs_state_df: pd.DataFrame) -> pd.DataFrame:
    """
    Create a simple mock action qpos DataFrame from observation qpos columns.

    In a real teleoperation dataset, action would come from the command stream.
    Here we use observed qpos as a placeholder action to keep the dataset API usable.
    """
    qpos_cols = [f"qpos_{joint}" for joint in JOINT_COLUMNS]
    action = obs_state_df[qpos_cols].copy()
    action.columns = JOINT_COLUMNS
    return action.astype("float32")


# fps convert to period(ns)
def generate_camera_timestamps(start_ns: int, end_ns: int, fps: float) -> List[int]:
    period_ns = int(1_000_000_000 / fps)
    return list(range(start_ns, end_ns + 1, period_ns))


def make_mock_image(camera_name: str, timestamp_ns: int, frame_index: int, size=(960, 600)) -> Image.Image:
    """
    Generate a deterministic RGB JPEG frame.

    The image content includes camera name, frame index, and timestamp so the
    stream can be inspected visually during review.
    """
    width, height = size
    base = np.zeros((height, width, 3), dtype=np.uint8)

    # Deterministic background pattern based on camera and frame index.
    camera_hash = sum(ord(c) for c in camera_name) % 255
    base[:, :, 0] = (camera_hash + frame_index * 3) % 255
    base[:, :, 1] = (frame_index * 7) % 255
    base[:, :, 2] = (camera_hash * 2 + frame_index * 5) % 255

    img = Image.fromarray(base, mode="RGB")
    draw = ImageDraw.Draw(img)

    text = f"{camera_name}\nframe={frame_index}\nts_ns={timestamp_ns}"
    draw.text((30, 30), text, fill=(255, 255, 255))

    return img


def write_camera_streams(dataset_root: Path, episode_id: str, start_ns: int, end_ns: int) -> Dict[str, int]:
    """
    Generate image streams via make_mock_image & generate_camera_timestamps
    """
    camera_root = dataset_root / "episodes" / episode_id / "cameras"
    frame_counts = {}

    for camera_name, fps in CAMERA_FPS.items():
        camera_dir = camera_root / camera_name
        # directory: dataset/episodes/<id>/cameras/<camera_name>
        camera_dir.mkdir(parents=True, exist_ok=True)

        timestamps = generate_camera_timestamps(start_ns, end_ns, fps)
        frame_counts[camera_name] = len(timestamps)

        for idx, ts in enumerate(timestamps):
            img = make_mock_image(camera_name=camera_name, timestamp_ns=ts, frame_index=idx)
            img.save(camera_dir / f"{ts}.jpeg", format="JPEG", quality=90)

    return frame_counts


def write_metadata(dataset_root: Path, episode_id: str, frame_counts: Dict[str, int]) -> None:
    """
    Write a metadata.yaml compatible with the OpenArm Dataset concepts.

    The fields mirror the documented API concepts:
    - version
    - operator
    - operation_type
    - location
    - tasks
    - episodes
    - num_episodes
    - equipment :- id / version / embodiments / perceptions :- cameras
    - frequencies :- action / cameras / obs 
    """
    metadata = {
        "version": "0.3.0",
        "operator": "mock_operator",
        "operation_type": "teleop",
        "location": "mock_ubuntu_server_22_04",
        "tasks": [
            {
                "prompt": "Mock synchronized OpenArm data collection.",
                "description": "Synthetic two-arm joint states and four simulated camera streams.",
            }
        ],
        "episodes": [
            {
                "id": episode_id,
                "success": True,
                "task_index": 0,
            }
        ],
        "equipment": {
            "id": "MockOpenArm",
            "version": "0.1.0",
            "embodiments": {
                "arms": {
                    "id": "OpenArm",
                    "version": "2.0",
                }
            },
            "perceptions": {
                "cameras": {
                    name: {
                        "id": "MockCamera",
                        "fps": CAMERA_FPS[name],
                        "num_frames": frame_counts[name],
                    }
                    for name in CAMERA_FPS
                }
            },
        },
        "frequencies": {
            "obs": 100,
            "action": 100,
            "cameras": CAMERA_FPS,
        },
    }

    with (dataset_root / "metadata.yaml").open("w", encoding="utf-8") as f:
        yaml.safe_dump(metadata, f, sort_keys=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--joint-states",
        type=str,
        default="data/joint_states_mock.jsonl",
        help="Path to Task 2 joint-state JSONL.",
    )
    parser.add_argument(
        "--output-root",
        type=str,
        default="data/openarm_mock_dataset",
        help="Output OpenArm Dataset-style root.",
    )
    parser.add_argument(
        "--episode-id",
        type=str,
        default="0",
        help="Episode ID. Default: 0.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Delete output-root before writing.",
    )
    args = parser.parse_args()

    joint_path = Path(args.joint_states)
    dataset_root = Path(args.output_root)

    if args.overwrite and dataset_root.exists():
        shutil.rmtree(dataset_root) # clean up old data

    dataset_root.mkdir(parents=True, exist_ok=True)

    # calculate start timestamp and end timestamp
    records = load_joint_states(joint_path)
    start_ns = min(int(r["sensor_timestamp_ns"]) for r in records)
    end_ns = max(int(r["sensor_timestamp_ns"]) for r in records)

    episode_root = dataset_root / "episodes" / args.episode_id
    obs_root = episode_root / "obs" / "arms"
    action_root = episode_root / "action" / "arms"

    # construct Parquet files for states and actions for both right and left arm
    for arm_name in ["left", "right"]:
        state_df = make_arm_dataframe(records, arm_name=arm_name)

        obs_dir = obs_root / arm_name
        obs_dir.mkdir(parents=True, exist_ok=True)
        state_df.to_parquet(obs_dir / "state.parquet")

        action_df = make_action_dataframe(state_df)
        action_dir = action_root / arm_name
        action_dir.mkdir(parents=True, exist_ok=True)
        action_df.to_parquet(action_dir / "qpos.parquet")

    frame_counts = write_camera_streams(
        dataset_root=dataset_root,
        episode_id=args.episode_id,
        start_ns=start_ns,
        end_ns=end_ns,
    )

    write_metadata(dataset_root=dataset_root, episode_id=args.episode_id, frame_counts=frame_counts)

    print("[MOCK MODE] Wrote OpenArm Dataset-style mock episode")
    print(f"[MOCK MODE] dataset_root={dataset_root}")
    print(f"[MOCK MODE] episode_id={args.episode_id}")
    print(f"[MOCK MODE] time_range_ns=({start_ns}, {end_ns})")
    print(f"[MOCK MODE] camera_frame_counts={frame_counts}")
    print()
    print("[MOCK MODE] Next verification:")
    print(f"  python3 -c \"import openarm_dataset; ds=openarm_dataset.Dataset('{dataset_root}'); print(ds.num_episodes); print(ds.camera_names); print(ds.sample(30, 0)[0])\"")


if __name__ == "__main__":
    main()