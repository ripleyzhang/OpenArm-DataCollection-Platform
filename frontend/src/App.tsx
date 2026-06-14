import { useEffect, useState } from "react";
import {
  fetchCameraPreview,
  fetchEpisodes,
  fetchJointStates,
  fetchRecordingStatus,
  startRecording,
  stopRecording,
} from "./api";
import type { EpisodeSummary, JointState, RecordingStatus } from "./types";

const CAMERAS = ["wrist_left", "wrist_right", "ceiling", "head"];

export default function App() {
  const [episodes, setEpisodes] = useState<EpisodeSummary[]>([]);
  const [jointStates, setJointStates] = useState<JointState[]>([]);
  const [recording, setRecording] = useState<RecordingStatus>({
    is_recording: false,
    started_at_ns: null,
  });

  const [selectedCamera, setSelectedCamera] = useState("wrist_left");
  const [cameraImage, setCameraImage] = useState<string | null>(null);
  const [cameraTimestamp, setCameraTimestamp] = useState<number | null>(null);

  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      setError(null);

      const [episodeData, jointData, recordingData] = await Promise.all([
        fetchEpisodes(),
        fetchJointStates(),
        fetchRecordingStatus(),
      ]);

      setEpisodes(episodeData);
      setJointStates(jointData.joint_states);
      setRecording(recordingData);

      try {
        const preview = await fetchCameraPreview(selectedCamera);
        setCameraImage(`data:${preview.mime_type};base64,${preview.image_base64}`);
        setCameraTimestamp(preview.timestamp_ns);
      } catch {
        setCameraImage(null);
        setCameraTimestamp(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    }
  }

  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, 1000);
    return () => window.clearInterval(timer);
  }, [selectedCamera]);

  async function handleRecordingClick() {
    try {
      const result = recording.is_recording
        ? await stopRecording()
        : await startRecording();

      setRecording(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update recording state");
    }
  }

  const leftArm = jointStates.filter((state) => state.arm_name === "left");
  const rightArm = jointStates.filter((state) => state.arm_name === "right");

  return (
    <main style={styles.page}>
      <header style={styles.header}>
        <div>
          <h1 style={styles.title}>Mock OpenArm Dashboard</h1>
          <p style={styles.subtitle}>
            Live mock joint states, camera preview, episode count, and recording control.
          </p>
        </div>

        <button
          onClick={handleRecordingClick}
          style={{
            ...styles.button,
            backgroundColor: recording.is_recording ? "#b91c1c" : "#166534",
          }}
        >
          {recording.is_recording ? "Stop Recording" : "Start Recording"}
        </button>
      </header>

      {error && <div style={styles.error}>Error: {error}</div>}

      <section style={styles.cards}>
        <MetricCard label="Recording" value={recording.is_recording ? "ON" : "OFF"} />
        <MetricCard label="Episodes" value={String(episodes.length)} />
        <MetricCard label="Joint States" value={String(jointStates.length)} />
      </section>

      <section style={styles.grid}>
        <div style={styles.panel}>
          <div style={styles.panelHeader}>
            <h2>Camera Preview</h2>

            <select
              value={selectedCamera}
              onChange={(event) => setSelectedCamera(event.target.value)}
              style={styles.select}
            >
              {CAMERAS.map((camera) => (
                <option key={camera} value={camera}>
                  {camera}
                </option>
              ))}
            </select>
          </div>

          <div style={styles.imageBox}>
            {cameraImage ? (
              <img src={cameraImage} alt={selectedCamera} style={styles.image} />
            ) : (
              <div style={styles.empty}>No camera preview available</div>
            )}
          </div>

          <p style={styles.smallText}>
            timestamp_ns: {cameraTimestamp ?? "-"}
          </p>
        </div>

        <div style={styles.panel}>
          <h2>Live Joint States</h2>

          <h3>Left Arm / can0</h3>
          <JointTable states={leftArm} />

          <h3>Right Arm / can1</h3>
          <JointTable states={rightArm} />
        </div>
      </section>
    </main>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div style={styles.card}>
      <div style={styles.cardLabel}>{label}</div>
      <div style={styles.cardValue}>{value}</div>
    </div>
  );
}

function JointTable({ states }: { states: JointState[] }) {
  if (states.length === 0) {
    return <p style={styles.smallText}>No joint states available.</p>;
  }

  return (
    <table style={styles.table}>
      <thead>
        <tr>
          <th style={styles.th}>Joint</th>
          <th style={styles.th}>Position</th>
          <th style={styles.th}>Velocity</th>
          <th style={styles.th}>Torque</th>
        </tr>
      </thead>

      <tbody>
        {states.map((state) => (
          <tr key={`${state.interface}-${state.joint_name}`}>
            <td style={styles.td}>{state.joint_name}</td>
            <td style={styles.td}>{state.position_rad.toFixed(4)}</td>
            <td style={styles.td}>{state.velocity_rad_s.toFixed(4)}</td>
            <td style={styles.td}>{state.torque_nm.toFixed(4)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    minHeight: "100vh",
    padding: "32px",
    fontFamily: "Arial, sans-serif",
    background: "#f8fafc",
    color: "#0f172a",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    gap: "24px",
    alignItems: "center",
    marginBottom: "24px",
  },
  title: {
    margin: 0,
    fontSize: "30px",
  },
  subtitle: {
    marginTop: "8px",
    color: "#475569",
  },
  button: {
    color: "white",
    border: "none",
    borderRadius: "10px",
    padding: "14px 20px",
    fontSize: "16px",
    cursor: "pointer",
  },
  error: {
    background: "#fee2e2",
    color: "#991b1b",
    padding: "12px",
    borderRadius: "8px",
    marginBottom: "16px",
  },
  cards: {
    display: "grid",
    gridTemplateColumns: "repeat(3, 1fr)",
    gap: "16px",
    marginBottom: "24px",
  },
  card: {
    background: "white",
    padding: "18px",
    borderRadius: "12px",
    boxShadow: "0 1px 3px rgba(15, 23, 42, 0.12)",
  },
  cardLabel: {
    color: "#64748b",
    fontSize: "14px",
  },
  cardValue: {
    fontSize: "32px",
    fontWeight: 700,
    marginTop: "8px",
  },
  grid: {
    display: "grid",
    gridTemplateColumns: "1fr 1.3fr",
    gap: "16px",
  },
  panel: {
    background: "white",
    padding: "18px",
    borderRadius: "12px",
    boxShadow: "0 1px 3px rgba(15, 23, 42, 0.12)",
  },
  panelHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  select: {
    padding: "8px",
    borderRadius: "8px",
  },
  imageBox: {
    marginTop: "12px",
    minHeight: "320px",
    background: "#020617",
    borderRadius: "12px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
  },
  image: {
    width: "100%",
    display: "block",
  },
  empty: {
    color: "#cbd5e1",
  },
  smallText: {
    color: "#64748b",
    fontSize: "13px",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    marginBottom: "16px",
  },
  th: {
    textAlign: "left",
    borderBottom: "1px solid #e2e8f0",
    padding: "8px",
    color: "#475569",
  },
  td: {
    borderBottom: "1px solid #e2e8f0",
    padding: "8px",
  },
};