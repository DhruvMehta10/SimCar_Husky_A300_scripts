# Husky A300 Scripts

Movement and IMU-logging scripts for a Clearpath Husky A300 UGV, used as a
mobile instrumentation platform for structural health monitoring (SHM) work.

Robot namespace: `/a300_00075`
Communication: laptop connected to the robot over Wi-Fi (ROS 2 / `rclpy`).

---

## How to use this repo (offline workflow)

The machine running MobaXterm (which talks to the robot) is kept **off the
internet**. This repo is not cloned or pulled on that machine. The process is:

1. On an internet-connected machine, browse this repo on GitHub and open the
   script you need.
2. Read it, and tweak parameters if required (e.g. `SPEED`, `DISTANCE`, or the
   `--imu-topic` you pass at runtime).
3. Copy the full script text and paste it into an editor on the offline
   MobaXterm machine, then save it as a `.py` file.
4. Run it with `python3 <script>.py`.

Copy-paste notes:

- The scripts are self-contained — only ROS 2 imports, nothing custom to
  install — so pasting the single file is all that's needed.
- Pasting into **vim**: run `:set paste` first, then paste, then `:set nopaste`.
  Otherwise auto-indent will mangle the Python indentation. **nano** has no such
  issue.
- Maintaining the repo (commit/push) happens on the online machine, not on the
  offline robot-control machine.

---

## Connecting to the robot (SSH via MobaXterm)

The scripts run on the robot's **onboard computer**. From a new PC, you reach it
by opening an SSH session to the robot in MobaXterm.

Known values for this robot:

- Username: `robot`
- Hostname: `cpr-a300-00075`
- Port: `22` (default SSH)
- IP address and password: get these from the lab/team — they are not stored
  in this repo.

Before connecting, make sure your PC is on the **same network as the robot**
(join the Husky's Wi-Fi / LAN). This is a local network and is separate from the
internet.

Steps in MobaXterm:

1. Click **Session** (top-left) → **SSH**.
2. **Remote host:** the robot's IP address (e.g. `192.168.x.x`), or try the
   hostname `cpr-a300-00075` if your network resolves it.
3. Tick **Specify username** and enter `robot`.
4. Leave **Port** as `22`.
5. Click **OK**, then enter the password when prompted. (MobaXterm can offer to
   save the session so you don't re-enter the host/username next time.)

Once connected, confirm you're talking to the robot's ROS 2 graph:

```bash
ros2 topic list
```

You should see the `/a300_00075/...` topics (e.g. `/a300_00075/cmd_vel`,
`/a300_00075/platform/odom`, `/a300_00075/sensors/imu_0/data_raw`). If that list
comes up, you're in and ready to paste and run a script.

Finding the robot's IP if you don't have it:

- Check the robot's onboard display, if fitted.
- Ping the hostname: `ping cpr-a300-00075` (works if the network resolves it).
- Check the Wi-Fi router / access point's list of connected devices.

---

## Confirmed topics

These were verified on the robot with `ros2 topic list` / `ros2 topic info`:

| Purpose            | Topic                                   | Message type          |
|--------------------|-----------------------------------------|-----------------------|
| Velocity command   | `/a300_00075/cmd_vel`                   | `geometry_msgs/TwistStamped` |
| Odometry           | `/a300_00075/platform/odom`             | `nav_msgs/Odometry`   |
| IMU (fused)        | `/a300_00075/sensors/imu_0/data`        | `sensor_msgs/Imu`     |
| IMU (raw)          | `/a300_00075/sensors/imu_0/data_raw`    | `sensor_msgs/Imu`     |

`cmd_vel` is the top-level input to the twist_mux (preferred over the
`joy_teleop`, `rc_teleop`, and `platform/cmd_vel` variants).

For vibration/SHM analysis, prefer **`data_raw`** — the unfiltered
accelerometer/gyro output with no orientation filter in the signal path.
The `data` topic additionally carries a fused orientation quaternion but is
processed. On `data_raw`, the orientation (`qx..qw`) columns are not valid
and can be ignored.

---

## Scripts

### `husky_move_simple.py`
Minimal script: drive forward a set distance at a set speed using odometry.
Edit the two constants at the top, then run.

```bash
python3 husky_move_simple.py
```

- `SPEED` — m/s (set negative to reverse)
- `DISTANCE` — metres
- `TOL` — stopping tolerance (default 2 cm)

### `husky_move_and_record.py`
Drive a set distance at a set speed **and** log the IMU to a CSV for the whole
run. Recording starts on node startup and stops automatically at the target
distance. Each row is tagged with a `phase` column (`idle` / `driving` / `done`)
so the moving segment can be isolated in analysis. Prints a throttled (~5 Hz)
live acceleration readout to the console while driving.

```bash
python3 husky_move_and_record.py --distance 2.0 --speed 0.25 \
    --imu-topic /a300_00075/sensors/imu_0/data_raw
```

| Argument       | Default                              | Notes                          |
|----------------|--------------------------------------|--------------------------------|
| `--distance`   | `1.0`                                | metres                         |
| `--speed`      | `0.15`                               | m/s                            |
| `--reverse`    | off                                  | drive backward                 |
| `--imu-topic`  | `/a300_00075/sensors/imu_0/data`     | use `..._raw` for vibration    |
| `--output`     | `imu_<timestamp>.csv`                | output CSV path                |

### `husky_imu_recorder.py`
Standalone IMU-to-CSV recorder. Records until `Ctrl+C`. Useful for a stationary
baseline, or run it in one terminal while driving from another.

```bash
python3 husky_imu_recorder.py --imu-topic /a300_00075/sensors/imu_0/data_raw \
    --output baseline.csv
```

---

## CSV format

Recording scripts write these columns:

| Column              | Meaning                                        |
|---------------------|------------------------------------------------|
| `t_ros`             | IMU header timestamp, seconds (sensor clock)   |
| `t_wall`            | Wall-clock receive time, seconds               |
| `phase`             | `idle` / `driving` / `done` (move+record only) |
| `qx, qy, qz, qw`    | Orientation quaternion (only valid on `data`)  |
| `wx, wy, wz`        | Angular velocity, rad/s                        |
| `ax, ay, az`        | Linear acceleration, m/s^2 (the vibration signal) |

At rest on a level surface, total acceleration magnitude sits near 9.81
(gravity); `az` holds most of the gravity component. The dynamic signal is the
deviation from that baseline.

---

## Verifying topics on the robot

Before a run, confirm the IMU topic name, type, and rate:

```bash
ros2 topic list | grep -i imu
ros2 topic info /a300_00075/sensors/imu_0/data_raw
ros2 topic hz   /a300_00075/sensors/imu_0/data_raw
```

The publish rate sets the Nyquist limit (usable band is roughly half the rate).
The onboard MEMS IMU is a different instrument class than the dedicated
accelerometer/DAQ chain — good for low-frequency content, but check the rate to
know the trustworthy band.

---

## Notes

- Movement commands are only published while odometry messages arrive; if odom
  drops out, the robot coasts to a stop on the controller's own command timeout.
- Start speeds low (0.1–0.15 m/s) when testing new parameters.
- Recorded `imu_*.csv` files are excluded from version control via `.gitignore`.
