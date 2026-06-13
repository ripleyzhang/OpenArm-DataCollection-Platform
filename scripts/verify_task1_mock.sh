#!/usr/bin/env bash
set -euo pipefail

export PATH="$PWD/scripts:$PATH"

echo "===== Task 1 Mock Verification ====="
date -Iseconds

echo
echo "===== Reset virtual CAN interfaces ====="
sudo modprobe vcan

sudo ip link set can0 down || true
sudo ip link set can1 down || true
sudo ip link delete can0 || true
sudo ip link delete can1 || true

sudo ip link add dev can0 type vcan
sudo ip link add dev can1 type vcan

sudo ip link set can0 up
sudo ip link set can1 up

echo
echo "===== Interface status after vcan setup ====="
ip -details link show can0
ip -details link show can1

echo
echo "===== Mock OpenArm CAN-FD configuration ====="
openarm-can-cli can_configure can0
openarm-can-cli can_configure can1

echo
echo "===== Mock zero position ====="
openarm-can-cli zero can0
openarm-can-cli zero can1

echo
echo "===== Mock state ====="
openarm-can-cli status can0
openarm-can-cli status can1

echo
echo "===== Task 1 mock verification completed ====="
