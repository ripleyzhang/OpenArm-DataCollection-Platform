from pathlib import Path

import openarm_dataset
import pandas as pd


DATASET_ROOT = Path("data/openarm_mock_dataset")
EXPECTED_CAMERAS = {"wrist_left", "wrist_right", "ceiling", "head"}
EPISODE = {"id": "0"}


def test_openarm_mock_dataset_exists():
    assert DATASET_ROOT.exists()
    assert (DATASET_ROOT / "metadata.yaml").exists()
    assert (DATASET_ROOT / "episodes" / "0").exists()


def test_openarm_dataset_api_can_load_cameras():
    dataset = openarm_dataset.Dataset(str(DATASET_ROOT))

    assert dataset.num_episodes >= 1

    cameras = dataset.load_cameras(EPISODE)

    assert set(cameras.keys()) == EXPECTED_CAMERAS

    for camera_name, camera in cameras.items():
        timestamps = camera.load_timestamps()
        assert len(timestamps) > 0, f"{camera_name} has no frames"
        assert timestamps == sorted(timestamps), f"{camera_name} timestamps are not sorted"


def test_openarm_dataset_has_joint_state_files():
    left_state = DATASET_ROOT / "episodes" / "0" / "obs" / "arms" / "left" / "state.parquet"
    right_state = DATASET_ROOT / "episodes" / "0" / "obs" / "arms" / "right" / "state.parquet"

    assert left_state.exists()
    assert right_state.exists()

    left_df = pd.read_parquet(left_state)
    right_df = pd.read_parquet(right_state)

    assert len(left_df) > 0
    assert len(right_df) > 0

    for prefix in ["qpos_", "qvel_", "qtorque_"]:
        assert any(col.startswith(prefix) for col in left_df.columns), left_df.columns
        assert any(col.startswith(prefix) for col in right_df.columns), right_df.columns