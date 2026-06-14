from pathlib import Path

import openarm_dataset


def test_openarm_mock_dataset_exists():
    root = Path("data/openarm_mock_dataset")
    assert root.exists()
    assert (root / "metadata.yaml").exists()
    assert (root / "episodes" / "0").exists()


def test_openarm_dataset_api_can_load_cameras():
    dataset = openarm_dataset.Dataset("data/openarm_mock_dataset")

    assert dataset.num_episodes >= 1

    cameras = dataset.load_cameras(0)
    assert set(cameras.keys()) == {"wrist_left", "wrist_right", "ceiling", "head"}

    for camera in cameras.values():
        assert camera.num_frames > 0
        timestamps = camera.load_timestamps()
        assert timestamps == sorted(timestamps)


def test_openarm_dataset_api_can_sample():
    dataset = openarm_dataset.Dataset("data/openarm_mock_dataset")
    samples = dataset.sample(hz=30, episode_index=0)

    assert len(samples) > 0

    sample = samples[0]
    assert set(sample.cameras.keys()) == {"wrist_left", "wrist_right", "ceiling", "head"}

    assert "arms/left/qpos" in sample.obs
    assert "arms/right/qpos" in sample.obs
    assert sample.obs["arms/left/qpos"].shape == (8,)
    assert sample.obs["arms/right/qpos"].shape == (8,)