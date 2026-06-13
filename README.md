## Task 1 — CAN-FD Interface Setup

### Real hardware procedure

In a real OpenArm setup, `can0` and `can1` would be physical SocketCAN interfaces exposed by USB-CAN FD adapters. Each OpenArm arm requires a dedicated CAN interface. The expected CAN-FD configuration is 1 Mbps nominal bitrate and 5 Mbps data bitrate, with CAN-FD enabled.

Commands:

```bash
sudo ip link set can0 down || true
sudo ip link set can1 down || true

sudo openarm-can-configure-socketcan can0 -fd
sudo openarm-can-configure-socketcan can1 -fd

openarm-can-cli can_configure can0
openarm-can-cli can_configure can1

openarm-can-cli zero can0
openarm-can-cli zero can1

ip -details link show can0
ip -details link show can1
```

### Mock procedure
Because I do not have physical OpenArm hardware or a USB-CAN FD adapter, I implemented Task 1 in mock mode using Linux virtual CAN interfaces.

## Task 2 
### Real hardware procedure

Damiao motors -> CAN-FD -> SocketCAN can0/can1 -> openarm_can -> joint states

### Mock

mock_damiao_stream.py -> vcan can0/can1 -> read_joint_states.py -> joint states