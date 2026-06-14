from __future__ import annotations

import shutil
import zipfile
from pathlib import Path
from typing import Any

import yaml


class EpisodeNotFoundError(FileNotFoundError):
    pass


def load_dataset_metadata(dataset_root: Path) -> dict[str, Any]:
    metadata_path = dataset_root / "metadata.yaml"

    if not metadata_path.exists():
        raise FileNotFoundError(f"metadata.yaml not found: {metadata_path}")

    with metadata_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if data is None:
        return {}

    return data


def list_episode_ids(dataset_root: Path) -> list[str]:
    episodes_root = dataset_root / "episodes"

    if not episodes_root.exists():
        return []

    episode_ids = [
        path.name
        for path in episodes_root.iterdir()
        if path.is_dir()
    ]

    return sorted(episode_ids, key=lambda x: int(x) if x.isdigit() else x)


def get_episode_path(dataset_root: Path, episode_id: str) -> Path:
    episode_path = dataset_root / "episodes" / episode_id

    if not episode_path.exists() or not episode_path.is_dir():
        raise EpisodeNotFoundError(f"Episode not found: {episode_id}")

    return episode_path


def get_episode_metadata(dataset_root: Path, episode_id: str) -> dict[str, Any]:
    metadata = load_dataset_metadata(dataset_root)
    episodes = metadata.get("episodes", [])

    matched = None
    for episode in episodes:
        if str(episode.get("id")) == str(episode_id):
            matched = episode
            break

    if matched is None:
        get_episode_path(dataset_root, episode_id)
        matched = {"id": episode_id}

    episode_path = get_episode_path(dataset_root, episode_id)

    camera_root = episode_path / "cameras"
    camera_counts = {}

    if camera_root.exists():
        for camera_dir in sorted(camera_root.iterdir()):
            if camera_dir.is_dir():
                camera_counts[camera_dir.name] = len(list(camera_dir.glob("*.jpeg")))

    return {
        "episode": matched,
        "episode_id": episode_id,
        "path": str(episode_path),
        "camera_frame_counts": camera_counts,
        "has_obs": (episode_path / "obs").exists(),
        "has_action": (episode_path / "action").exists(),
        "has_cameras": camera_root.exists(),
        "dataset_version": metadata.get("version"),
        "task": _task_for_episode(metadata, matched),
    }


def _task_for_episode(metadata: dict[str, Any], episode: dict[str, Any]) -> dict[str, Any] | None:
    task_index = episode.get("task_index")

    if task_index is None:
        return None

    tasks = metadata.get("tasks", [])

    try:
        return tasks[int(task_index)]
    except (IndexError, TypeError, ValueError):
        return None


def create_episode_zip(dataset_root: Path, episode_id: str, output_dir: Path) -> Path:
    episode_path = get_episode_path(dataset_root, episode_id)

    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / f"episode_{episode_id}.zip"

    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        metadata_path = dataset_root / "metadata.yaml"
        if metadata_path.exists():
            zf.write(metadata_path, arcname="metadata.yaml")

        for path in episode_path.rglob("*"):
            if path.is_file():
                arcname = path.relative_to(dataset_root)
                zf.write(path, arcname=str(arcname))

    return zip_path


def reset_generated_zip_dir(zip_dir: Path) -> None:
    if zip_dir.exists():
        shutil.rmtree(zip_dir)
    zip_dir.mkdir(parents=True, exist_ok=True)