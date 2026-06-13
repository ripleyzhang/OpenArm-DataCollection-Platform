#!usr/bin/bin/env/ python3
"""
Mock Damiao motor feedback stream.

This script simulates two OpenArm arms over two SocketCAN interfaces:

- can0 = left arm / arm_0
- can1 = right arm / arm_1

Each arm has 8 motors:
- J1-J7: arm joints
- J8: gripper

Motor ID layout per CAN bus:
- J1 sender CAN ID = 0x01, receiver/master ID = 0x11
- J2 sender CAN ID = 0x02, receiver/master ID = 0x12
- ...
- J8 sender CAN ID = 0x08, receiver/master ID = 0x18

Because can0 and can1 are separate CAN buses, the same CAN IDs can be reused
on both interfaces without collision.

Mock feedback frame format:
- arbitration_id: receiver/master ID, e.g. 0x11-0x18
- payload: little-endian packed values

    uint64 timestamp_ns
    uint8  arm_index
    uint8  joint_index
    uint8  sender_can_id
    uint8  receiver_can_id
    float32 position_rad
    float32 velocity_rad_s
    float32 torque_nm

Payload length: 24 bytes.
"""
import argparse
import math
import signal
import struct
import time
from dataclasses import dataclass
from typing import Dict, List

import can


@dataclass(frozen=True)
class MotorConfig:
    arm_name: str          # "left" or "right"
    arm_index: int         # 0 for can0 arm, 1 for can1 arm
    interface: str         # "can0" or "can1"
    joint_name: str        # "J1" ... "J8_gripper"
    joint_index: int       # 1 ... 8
    sender_can_id: int     # motor sender CAN ID: 0x01 ... 0x08
    receiver_can_id: int   # receiver/master ID: 0x11 ... 0x18
    phase: float           # phase offset for synthetic trajectory

MOTORS: List[MotorConfig] = [
    # left arm config (arm_name="left", arm_index=0, interface="can0", phase_offset=0.0)
    MotorConfig("left", 0, "can0", "J1", 1, 0x01, 0x11, phase=0.0 + 0.35 * 0),
    MotorConfig("left", 0, "can0", "J2", 2, 0x02, 0x12, phase=0.0 + 0.35 * 1),
    MotorConfig("left", 0, "can0", "J3", 3, 0x03, 0x13, phase=0.0 + 0.35 * 2),
    MotorConfig("left", 0, "can0", "J4", 4, 0x04, 0x14, phase=0.0 + 0.35 * 3),
    MotorConfig("left", 0, "can0", "J5", 5, 0x05, 0x15, phase=0.0 + 0.35 * 4),
    MotorConfig("left", 0, "can0", "J6", 6, 0x06, 0x16, phase=0.0 + 0.35 * 5),
    MotorConfig("left", 0, "can0", "J7", 7, 0x07, 0x17, phase=0.0 + 0.35 * 6),
    MotorConfig("left", 0, "can0", "J8_gripper", 8, 0x08, 0x18, phase=0.0 + 0.35 * 7),

    # right arm config (arm_name="right", arm_index=1, interface="can1", phase_offset=1.5)
    MotorConfig("right", 1, "can1", "J1", 1, 0x01, 0x11, phase=1.5 + 0.35 * 0),
    MotorConfig("right", 1, "can1", "J2", 2, 0x02, 0x12, phase=1.5 + 0.35 * 1),
    MotorConfig("right", 1, "can1", "J3", 3, 0x03, 0x13, phase=1.5 + 0.35 * 2),
    MotorConfig("right", 1, "can1", "J4", 4, 0x04, 0x14, phase=1.5 + 0.35 * 3),
    MotorConfig("right", 1, "can1", "J5", 5, 0x05, 0x15, phase=1.5 + 0.35 * 4),
    MotorConfig("right", 1, "can1", "J6", 6, 0x06, 0x16, phase=1.5 + 0.35 * 5),
    MotorConfig("right", 1, "can1", "J7", 7, 0x07, 0x17, phase=1.5 + 0.35 * 6),
    MotorConfig("right", 1, "can1", "J8_gripper", 8, 0x08, 0x18, phase=1.5 + 0.35 * 7),
]

running = True


def handle_signal(signum, frame):
    global running
    running = False


def generate_joint_state(motor: MotorConfig, t: float):
    """
    Generate smooth synthetic joint state for one motor.

    position_rad:
        Smooth sinusoidal joint position.

    velocity_rad_s:
        Analytical derivative of the position signal.

    torque_nm:
        Bounded synthetic torque signal.

    For the gripper, the position range is smaller because gripper motion is
    usually not represented like a full revolute arm joint.
    """
    frequency_hz = 0.2
    omega = 2.0 * math.pi * frequency_hz

    if motor.joint_name == "J8_gripper":
        # Smaller mock range for gripper-like motion.
        amplitude = 0.25
        torque_amplitude = 0.15
    else:
        amplitude = 1.0
        torque_amplitude = 0.5

    position = amplitude * math.sin(omega * t + motor.phase)
    velocity = amplitude * omega * math.cos(omega * t + motor.phase)
    torque = torque_amplitude * math.sin(omega * t + motor.phase + 0.3)

    return position, velocity, torque

def make_feedback_frame(motor: MotorConfig, timestamp_ns: int, t: float) -> can.Message:
    position, velocity, torque = generate_joint_state(motor, t)

    payload = struct.pack(
        "<QBBBBfff",
        timestamp_ns,
        motor.arm_index,
        motor.joint_index,
        motor.sender_can_id,
        motor.receiver_can_id,
        float(position),
        float(velocity),
        float(torque),
    )

    return can.Message(
        arbitration_id=motor.receiver_can_id,
        data=payload,
        is_extended_id=False,
        is_fd=True,
        bitrate_switch=True,
    )



def main():
    parser = argparse.ArgumentParser(
        description="Mock two-arm OpenArm Damiao CAN-FD feedback stream."
    )
    parser.add_argument(
        "--rate-hz",
        type=float,
        # Each motor emits feedback at 100 Hz by default.
        default=100.0,
        help="Target feedback rate per motor. Default: 100 Hz.",
    )
    args = parser.parse_args()

    if args.rate_hz <= 0:
        raise ValueError("--rate-hz must be positive")

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    buses: Dict[str, can.BusABC] = {
        "can0": can.Bus(interface="socketcan", channel="can0", fd=True),
        "can1": can.Bus(interface="socketcan", channel="can1", fd=True),
    }

    period_s = 1.0 / args.rate_hz
    start_time = time.monotonic()

    print("[MOCK MODE] Starting two-arm OpenArm Damiao-style CAN-FD feedback stream")
    print(f"[MOCK MODE] rate_hz={args.rate_hz}")
    print("[MOCK MODE] can0 = left arm, 8 motors: J1-J7 + J8_gripper")
    print("[MOCK MODE] can1 = right arm, 8 motors: J1-J7 + J8_gripper")
    print("[MOCK MODE] CAN IDs per bus: sender 0x01-0x08, receiver/master 0x11-0x18")
    print("[MOCK MODE] Press Ctrl+C to stop")

    frame_count = 0

    try:
        while running:
            loop_start = time.monotonic()
            t = loop_start - start_time
            timestamp_ns = time.time_ns()

            for motor in MOTORS:
                msg = make_feedback_frame(motor, timestamp_ns, t)
                buses[motor.interface].send(msg)
                frame_count += 1

            elapsed = time.monotonic() - loop_start
            sleep_s = max(0.0, period_s - elapsed)
            time.sleep(sleep_s)

    finally:
        for bus in buses.values():
            bus.shutdown()

        print()
        print(f"[MOCK MODE] Stopped. Sent {frame_count} CAN-FD feedback frames.")


if __name__ == "__main__":
    main()