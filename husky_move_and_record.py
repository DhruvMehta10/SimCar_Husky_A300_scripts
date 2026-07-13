#!/usr/bin/env python3

"""
Drive the Husky A300 a fixed distance at a fixed speed (odometry-based)
while simultaneously logging the onboard IMU to a .csv file.

Recording starts as soon as the node comes up and stops automatically
when the target distance is reached, so the CSV covers the whole run.
Each IMU row is tagged with a "phase" column (idle / driving / done)
so you can crop the moving segment during analysis.

Robot namespace:
    /a300_00075

Examples:
    # defaults: 1.0 m forward at 0.15 m/s, auto-named CSV
    python3 husky_move_and_record.py

    # 2 m forward at 0.25 m/s
    python3 husky_move_and_record.py --distance 2.0 --speed 0.25

    # 1.5 m in reverse, custom IMU topic and output name
    python3 husky_move_and_record.py --distance 1.5 --reverse \
        --imu-topic /a300_00075/sensors/imu_0/data_raw \
        --output run01.csv

IMPORTANT: verify the IMU topic on your robot first:
    ros2 topic list | grep -i imu
    ros2 topic hz  <that topic>        # check the sample rate
"""

import csv
import math
import time
import argparse
from datetime import datetime

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import TwistStamped
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Imu


# ---------------------------------------------------------------------------
# Topic configuration (from your working out-and-back script)
# ---------------------------------------------------------------------------
NAMESPACE = "/a300_00075"
CMD_TOPIC = f"{NAMESPACE}/cmd_vel"
ODOM_TOPIC = f"{NAMESPACE}/platform/odom"
DEFAULT_IMU_TOPIC = f"{NAMESPACE}/sensors/imu_0/data"   # <-- verify this!

TOL = 0.02   # 2 cm distance tolerance


class MoveAndRecord(Node):

    def __init__(self, distance, speed, reverse, imu_topic, output):
        super().__init__("husky_move_and_record")

        # --- movement config ---
        self.distance = abs(distance)
        self.speed = abs(speed)
        self.direction = -1.0 if reverse else 1.0
        self.imu_topic = imu_topic

        self.phase = "idle"
        self.finished = False
        self.start_x = None
        self.start_y = None

        # --- CSV setup ---
        if output is None:
            output = f"imu_{datetime.now():%Y%m%d_%H%M%S}.csv"
        self.output = output
        self.csv_file = open(self.output, "w", newline="")
        self.writer = csv.writer(self.csv_file)
        self.writer.writerow([
            "t_ros",        # sensor timestamp from IMU header (seconds)
            "t_wall",       # wall-clock receive time (seconds)
            "phase",        # idle / driving / done
            "qx", "qy", "qz", "qw",     # orientation quaternion
            "wx", "wy", "wz",           # angular velocity (rad/s)
            "ax", "ay", "az",           # linear acceleration (m/s^2)
        ])
        self.n_samples = 0
        self.last_print = 0.0   # for throttling the live console readout

        # --- ROS I/O ---
        self.pub = self.create_publisher(TwistStamped, CMD_TOPIC, 10)
        self.odom_sub = self.create_subscription(
            Odometry, ODOM_TOPIC, self.odom_cb, 10)
        self.imu_sub = self.create_subscription(
            Imu, self.imu_topic, self.imu_cb, 50)

        self.get_logger().info(f"cmd_vel  -> {CMD_TOPIC}")
        self.get_logger().info(f"odom     <- {ODOM_TOPIC}")
        self.get_logger().info(f"imu      <- {self.imu_topic}")
        self.get_logger().info(f"output   -> {self.output}")
        self.get_logger().info(
            f"move: {self.distance:.3f} m at {self.speed:.3f} m/s "
            f"({'reverse' if reverse else 'forward'})")
        self.get_logger().info("Waiting for odometry...")

    # -----------------------------------------------------------------------
    # IMU logging
    # -----------------------------------------------------------------------
    def imu_cb(self, msg):
        if self.finished:
            return

        t_ros = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9

        self.writer.writerow([
            f"{t_ros:.9f}",
            f"{time.time():.9f}",
            self.phase,
            msg.orientation.x, msg.orientation.y,
            msg.orientation.z, msg.orientation.w,
            msg.angular_velocity.x, msg.angular_velocity.y, msg.angular_velocity.z,
            msg.linear_acceleration.x, msg.linear_acceleration.y, msg.linear_acceleration.z,
        ])

        self.n_samples += 1
        if self.n_samples % 100 == 0:
            self.csv_file.flush()

        # --- live console readout, throttled to ~5 Hz ---
        now = time.time()
        if now - self.last_print >= 0.2:
            self.last_print = now
            ax = msg.linear_acceleration.x
            ay = msg.linear_acceleration.y
            az = msg.linear_acceleration.z
            amag = math.sqrt(ax * ax + ay * ay + az * az)
            self.get_logger().info(
                f"[{self.phase:7s}] |a|={amag:6.3f}  "
                f"ax={ax:+6.3f} ay={ay:+6.3f} az={az:+6.3f} m/s^2  "
                f"(n={self.n_samples})")

    # -----------------------------------------------------------------------
    # Movement (odometry-driven, same pattern as your working script)
    # -----------------------------------------------------------------------
    def odom_cb(self, msg):
        if self.finished:
            return

        cx = msg.pose.pose.position.x
        cy = msg.pose.pose.position.y

        # First odometry message latches the start pose and begins the move
        if self.start_x is None:
            self.start_x = cx
            self.start_y = cy
            self.phase = "driving"
            self.get_logger().info("Odometry received — starting move")
            self.move()
            return

        dist = math.hypot(cx - self.start_x, cy - self.start_y)

        if dist >= self.distance - TOL:
            self.stop()
            self.phase = "done"
            self.finished = True
            self.get_logger().info(f"Reached {dist:.3f} m — stopping")
            raise SystemExit          # clean exit -> finalises the CSV
        else:
            self.move()

    def move(self):
        msg = TwistStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "base_link"
        msg.twist.linear.x = self.direction * self.speed
        msg.twist.angular.z = 0.0
        self.pub.publish(msg)

    def stop(self):
        msg = TwistStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "base_link"
        msg.twist.linear.x = 0.0
        msg.twist.angular.z = 0.0
        self.pub.publish(msg)

    def close(self):
        # publish a final stop and finalise the file
        try:
            self.stop()
        except Exception:
            pass
        if not self.csv_file.closed:
            self.csv_file.flush()
            self.csv_file.close()
        self.get_logger().info(
            f"Saved {self.n_samples} IMU samples to {self.output}")


def main():
    rclpy.init()

    parser = argparse.ArgumentParser(
        description="Move Husky A300 a set distance while recording IMU to CSV.")
    parser.add_argument("--distance", type=float, default=1.0,
                        help="distance to travel in metres (default 1.0)")
    parser.add_argument("--speed", type=float, default=0.15,
                        help="speed in m/s (default 0.15)")
    parser.add_argument("--reverse", action="store_true",
                        help="drive backward instead of forward")
    parser.add_argument("--imu-topic", default=DEFAULT_IMU_TOPIC,
                        help=f"IMU topic (default {DEFAULT_IMU_TOPIC})")
    parser.add_argument("--output", default=None,
                        help="output CSV path (default imu_<timestamp>.csv)")
    # parse_known_args so ROS args (--ros-args ...) don't cause errors
    parsed, _ = parser.parse_known_args()

    node = MoveAndRecord(
        parsed.distance, parsed.speed, parsed.reverse,
        parsed.imu_topic, parsed.output)

    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        node.close()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
