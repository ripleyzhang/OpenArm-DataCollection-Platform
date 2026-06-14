import type {
    CameraPreviewResponse,
    EpisodeSummary,
    JointStateResponse,
    RecordingStatus,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

async function requestJson<T>(path: string, options?: RequestInit): Promise<T> {
    const response = await fetch(`${API_BASE}${path}`, options);

    if (!response.ok) {
        const text = await response.text();
        throw new Error(`${response.status}: ${text}`);
    }

    return response.json() as Promise<T>;
}

export function fetchHealth(): Promise<unknown> {
    return requestJson<unknown>("/health");
}

export function fetchEpisodes(): Promise<EpisodeSummary[]> {
    return requestJson<EpisodeSummary[]>("/episodes");
}

export function fetchJointStates(): Promise<JointStateResponse> {
    return requestJson<JointStateResponse>("/live/joint-states");
}

export function fetchCameraPreview(camera: string): Promise<CameraPreviewResponse> {
    return requestJson<CameraPreviewResponse>(
        `/live/camera-preview?camera=${encodeURIComponent(camera)}`,
    );
}

export function fetchRecordingStatus(): Promise<RecordingStatus> {
    return requestJson<RecordingStatus>("/recording/status");
}

export function startRecording(): Promise<RecordingStatus> {
    return requestJson<RecordingStatus>("/recording/start", {
        method: "POST",
    });
}

export function stopRecording(): Promise<RecordingStatus> {
    return requestJson<RecordingStatus>("/recording/stop", {
        method: "POST",
    });
}