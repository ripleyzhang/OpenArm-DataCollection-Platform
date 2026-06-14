from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from storage import (
    EpisodeNotFoundError,
    create_episode_zip,
    get_episode_metadata,
    list_episode_ids,
    load_dataset_metadata,
)


def create_app(dataset_root: str | Path | None = None) -> FastAPI:
    if dataset_root is None:
        dataset_root = os.environ.get("OPENARM_DATASET_ROOT", "data/openarm_mock_dataset")

    dataset_root = Path(dataset_root)
    zip_output_dir = dataset_root / ".api_downloads"

    app = FastAPI(
        title="Mock OpenArm Data Collection API",
        version="0.1.0",
        description="REST API for listing, inspecting, and downloading mock OpenArm episodes.",
    )

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "dataset_root": str(dataset_root),
            "dataset_exists": dataset_root.exists(),
        }

    @app.get("/episodes")
    def list_episodes():
        try:
            metadata = load_dataset_metadata(dataset_root)
            episode_ids = list_episode_ids(dataset_root)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        episodes_by_id = {
            str(ep.get("id")): ep
            for ep in metadata.get("episodes", [])
        }

        result = []

        for episode_id in episode_ids:
            episode_meta = episodes_by_id.get(episode_id, {"id": episode_id})
            result.append(
                {
                    "episode_id": episode_id,
                    "success": episode_meta.get("success"),
                    "task_index": episode_meta.get("task_index"),
                    "metadata_url": f"/episodes/{episode_id}/metadata",
                    "download_url": f"/episodes/{episode_id}/download",
                }
            )

        return result

    @app.get("/episodes/{episode_id}/metadata")
    def episode_metadata(episode_id: str):
        try:
            return get_episode_metadata(dataset_root, episode_id)
        except EpisodeNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/episodes/{episode_id}/download")
    def download_episode(episode_id: str):
        try:
            zip_path = create_episode_zip(
                dataset_root=dataset_root,
                episode_id=episode_id,
                output_dir=zip_output_dir,
            )
        except EpisodeNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        return FileResponse(
            path=zip_path,
            filename=zip_path.name,
            media_type="application/zip",
        )

    return app


app = create_app()