from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from fastapi.middleware.cors import CORSMiddleware

import base64
import json
import random
import time

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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://vcm-53482.vm.duke.edu:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    recording_state = {
        "is_recording": False,
        "started_at_ns": None,
    }

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
    
    @app.get("/live/joint-states")
    def live_joint_states():
        """
        Return the latest simulated joint states for dashboard preview.

        In real hardware mode, this would be backed by the CAN reader / openarm_can.
        In mock mode, it reads the latest Task 2 JSONL records if available.
        """
        joint_path = Path("data/joint_states_mock.jsonl")

        if joint_path.exists():
            lines = joint_path.read_text(encoding="utf-8").splitlines()
            recent = []

            for line in reversed(lines[-200:]):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                recent.append(record)

                if len(recent) >= 16:
                    break

            return {
                "mode": "mock",
                "source": str(joint_path),
                "timestamp_ns": time.time_ns(),
                "joint_states": list(reversed(recent)),
            }

        # Fallback if Task 2 output does not exist yet.
        mock_states = []
        for arm_name, arm_index, interface in [
            ("left", 0, "can0"),
            ("right", 1, "can1"),
        ]:
            for joint_index in range(1, 9):
                joint_name = "J8_gripper" if joint_index == 8 else f"J{joint_index}"
                mock_states.append(
                    {
                        "host_received_ns": time.time_ns(),
                        "sensor_timestamp_ns": time.time_ns(),
                        "interface": interface,
                        "arm_name": arm_name,
                        "arm_index": arm_index,
                        "joint_name": joint_name,
                        "joint_index": joint_index,
                        "position_rad": round(random.uniform(-1.0, 1.0), 4),
                        "velocity_rad_s": round(random.uniform(-0.5, 0.5), 4),
                        "torque_nm": round(random.uniform(-0.2, 0.2), 4),
                    }
                )

        return {
            "mode": "mock_fallback",
            "timestamp_ns": time.time_ns(),
            "joint_states": mock_states,
        }

    @app.get("/live/camera-preview")
    def live_camera_preview(camera: str = "wrist_left"):
        """
        Return the latest simulated camera frame as base64 JPEG.

        In real hardware mode, this would come from the camera capture process.
        In mock mode, it reads from the OpenArm Dataset-style camera directory.
        """
        camera_dir = dataset_root / "episodes" / "0" / "cameras" / camera

        if not camera_dir.exists():
            return JSONResponse(
                status_code=404,
                content={
                    "error": f"Camera stream not found: {camera}",
                    "camera": camera,
                },
            )

        frames = sorted(camera_dir.glob("*.jpeg"))

        if not frames:
            return JSONResponse(
                status_code=404,
                content={
                    "error": f"No frames found for camera: {camera}",
                    "camera": camera,
                },
            )

        frame_path = frames[-1]
        encoded = base64.b64encode(frame_path.read_bytes()).decode("utf-8")

        return {
            "camera": camera,
            "timestamp_ns": int(frame_path.stem),
            "mime_type": "image/jpeg",
            "image_base64": encoded,
        }

    @app.post("/recording/start")
    def start_recording():
        if recording_state["is_recording"]:
            return {
                "status": "already_recording",
                "is_recording": True,
                "started_at_ns": recording_state["started_at_ns"],
            }

        recording_state["is_recording"] = True
        recording_state["started_at_ns"] = time.time_ns()

        return {
            "status": "started",
            "is_recording": True,
            "started_at_ns": recording_state["started_at_ns"],
        }


    @app.post("/recording/stop")
    def stop_recording():
        if not recording_state["is_recording"]:
            return {
                "status": "not_recording",
                "is_recording": False,
                "started_at_ns": None,
            }

        stopped_at_ns = time.time_ns()
        duration_ns = stopped_at_ns - int(recording_state["started_at_ns"])

        recording_state["is_recording"] = False
        recording_state["started_at_ns"] = None

        return {
            "status": "stopped",
            "is_recording": False,
            "stopped_at_ns": stopped_at_ns,
            "duration_ns": duration_ns,
        }


    @app.get("/recording/status")
    def recording_status():
        return recording_state

    return app


app = create_app()