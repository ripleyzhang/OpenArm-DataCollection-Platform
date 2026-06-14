export type JointState = {
    interface: string;
    arm_name: string;
    joint_name: string;
    joint_index: number;
    position_rad: number;
    velocity_rad_s: number;
    torque_nm: number;
};

export type JointStateResponse = {
    mode: string;
    timestamp_ns: number;
    joint_states: JointState[];
};

export type EpisodeSummary = {
    episode_id: string;
    success?: boolean;
    task_index?: number;
    metadata_url?: string;
    download_url?: string;
};

export type CameraPreviewResponse = {
    camera: string;
    timestamp_ns: number;
    mime_type: string;
    image_base64: string;
};

export type RecordingStatus = {
    is_recording: boolean;
    started_at_ns: number | null;
    status?: string;
};