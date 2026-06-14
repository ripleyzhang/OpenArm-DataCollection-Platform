# OpenArm Data Collection Platform
This repository implements a mockable data collection pipeline for the OpenArm 2.0 take-home project. 5 tasks are completed, including CAN-FD configuration, joint state data stream reading, camera frames synchronization, data storage backend and simple monitoring dashboard frontend.

Because I did not have access to the physical OpenArm 2.0 hardware, I mocked OpenArm CAN CLI interface, simulated Damiao motor data stream and cameras with different frame rates. 

## Completed Tasks
## Task 1 — CAN-FD Interface Setup
Completed in mock mode.

Implemented files:

scripts/verify_task1_mock.sh
scripts/openarm-can-cli

Teminal screenshot address: 
```bash
./artifacts/terminal.png
```

The platform configures two Linux SocketCAN interfaces: can0 for left arm and can1 for right arm.

For local and CI testing, I use Linux vcan interfaces to simulate the CAN-FD channels. The verification script brings up both interfaces and runs a mock openarm-can-cli command to simulate CAN configuration and zero-position setup.

The script verifies that both CAN interfaces are up and that mock zero-position state is recorded under mock_state/.

In a real hardware setup, this step would use physical CAN-FD adapters and the OpenArm CAN CLI Tool to configure can0 and can1.


## Task 2 — Live Joint State Reading
Completed in mock mode.

Implemented files:

scripts/mock_damiao_stream.py
scripts/read_joint_states.py
scripts/verify_task2_mock.sh

I implemented a simulated CAN-FD data stream for two OpenArm arms. Each arm has 8 motors, following the motor ID in the OpenArm motor table https://docs.openarm.dev/api-reference/setup/motor-id: 

- J1–J7: arm joints
- J8: gripper

The mock sender generates synthetic CAN-FD frames containing:

- timestamp(ns)
- arm_index
- joint_index
- sender_can_id
- receiver_can_id
- position(rad)
- velocity(rad/s)
- torque(nm)

The reader receives frames from can0 and can1, validates the IDs, decodes the payload, and writes structured joint states to:

data/joint_states_mock.jsonl

These mock data would be replaced by real openarm_can / SocketCAN motor feedback when physical hardware is available.

## Task 3 — Camera Synchronization
Completed in mock mode.

Implemented files:

scripts/simulate_cameras_openarm_dataset.py
scripts/verify_task3_mock.sh

The cameras are generated at different frame rates to simulate a realistic multi-camera system:

wrist_left:  30 FPS
wrist_right: 30 FPS
ceiling:     15 FPS
head:        60 FPS

Joint states are stored in parquet files, while camera frames are stored as timestamped JPEGs. The timestamp is used as the synchronization key rather than relying on frame index.

## Task 4 — Episode Storage Backend and REST API
Completed.

Implemented files:

src/storage.py
src/api.py
scripts/verify_task4_mock.sh

I implemented a file-based storage backend and FastAPI service for managing generated episodes.

The REST API exposes:

```
GET  /health
GET  /episodes
GET  /episodes/{episode_id}/metadata
GET  /episodes/{episode_id}/download
```

The storage backend can:

- list available episodes
- load dataset metadata
- retrieve per-episode metadata
- count camera frames per stream
- package an episode as a .zip file for download

## Task 5 — Web Dashboard
Completed as a minimal React + Vite + TypeScript dashboard.

The dashboard displays:

- current recording status
- episode count
- live/simulated joint states from can0 and can1
- camera preview from the generated mock dataset
- Start / Stop recording control

The frontend polls the backend periodically. In mock mode, the recording buttons update an in-memory backend recording state. In a real implementation, these buttons would start and stop a recorder process that writes a new episode.

## Data pipeline
Mock CAN-FD Stream -> Joint State Reader -> JSONL Joint State Log -> Mock Camera + Dataset Generator -> Episode Storage -> FastAPI Storage -> React Dashboard

## Design Decisions & Trade-offs
### Mock mode vs real hardware 
The system validates the software architecture and data flow, but it does not validate real motor behavior, real CAN-FD timing, real camera latency, or hardware failure modes.

The detailed hardware features are not mocked. True camera synchronization accuracy and physical motor communication reliability are not guarranted.

### Timestamp-based synchronization
The system uses timestamps as the primary synchronization mechanism between joint states and camera frames.

This is more robust than frame-index alignment because real robot systems often have dropped frames and different camera frame rates.

Each camera frame is stored with a timestamp in the filename, and each joint state record contains a timestamp field. A downstream sampler can align observations by nearest timestamp or resample the episode at a target control frequency.

### File storage vs. database
This take-home project is an initial and mocked project with small data stream. Storing data stream in a json file is suitable, portable and easy-cleanup. Database would add unnecessary complexity. A database can be added later for powerful searching and filtering.

### Minimal dashboard instead of a complex frontend
For Task 5, I built a minimal React + Vite + TypeScript dashboard in a short time. The goal was to demonstrate functionality rather than UI complexity.

## How to Run
```bash
# Install Python dependencies
python -m pip install --upgrade pip 
pip install -r requirements.txt

# varify task1-5
./scripts/verify_task1_mock.sh
./scripts/verify_task2_mock.sh
KEEP_GENERATED_DATA=1 ./scripts/verify_task3_mock.sh
KEEP_GENERATED_DATA=1 ./scripts/verify_task4_mock.sh

# backend
export PYTHONPATH="$PWD/src:$PYTHONPATH" 
export OPENARM_DATASET_ROOT="data/openarm_mock_dataset"
uvicorn api:app --host 0.0.0.0 --port 8000

http://127.0.0.1:8000/docs

# frontend
cd frontend 
npm install 
VITE_API_BASE=http://127.0.0.1:8000 npm run dev -- --host 0.0.0.0 --port 5173

http://127.0.0.1:5173
```

## What I Would Do Next With More Time or Hardware Access
With physical hardware access, I would replace the mock CAN sender with real openarm_can / SocketCAN reading from Damiao motor feedback.

In mock mode, joint states are generated from deterministic or random functions and are always well-formed. If I could get access to detailed hardware features, I will deal with real sensor noise, timing jitter, dropped frames, motor-specific behavior, bus errors, and true position/velocity/torque values. I will add a normalize or smooth function.

The current mock uses timestamp-based alignment. With hardware, I would measure and improve synchronization by using hardware timestamps if available, tracking camera capture latency, detecting dropped frames, supporting interpolation or nearest-neighbor alignment for joint states.

Dashboard will support monitoring system anomalies including missing motor feedback, camera stream failures, disk or storage pressure, and all kinds of health issues.

## References
https://github.com/enactic/openarm
https://github.com/enactic/openarm_dataset
https://github.com/enactic/openarm_can/
https://docs.openarm.dev/
