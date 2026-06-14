#!/usr/bin/env bash
set -euo pipefail

export PATH="$PWD/scripts:$PATH"

mkdir -p data

echo "===== Task 2 Mock Verification: CAN-FD Data Stream ====="
date -Iseconds

echo
echo "===== Reuse Task 1 mock CAN setup ====="
./scripts/verify_task1_mock.sh

echo
echo "===== Start mock Damiao stream ====="
python3 scripts/mock_damiao_stream.py --rate-hz 50 &
STREAM_PID=$!

cleanup() {
  echo
  echo "===== Stop mock stream ====="
  if kill -0 "$STREAM_PID" >/dev/null 2>&1; then
    kill "$STREAM_PID" || true
    wait "$STREAM_PID" || true
  fi
}

trap cleanup EXIT

sleep 1

echo
echo "===== Read joint states ====="
python3 scripts/read_joint_states.py \
  --duration-s 3 \
  --output data/joint_states_mock.jsonl \
  --print-every 500

echo
echo "===== Output preview ====="
head -n 5 data/joint_states_mock.jsonl

echo
echo "===== Frame count ====="
FRAME_COUNT=$(wc -l < data/joint_states_mock.jsonl)
echo "$FRAME_COUNT data/joint_states_mock.jsonl"

if [ "$FRAME_COUNT" -lt 100 ]; then
  echo "ERROR: expected at least 100 parsed frames, got $FRAME_COUNT"
  exit 1
fi

echo
echo "===== Task 2 mock verification completed ====="