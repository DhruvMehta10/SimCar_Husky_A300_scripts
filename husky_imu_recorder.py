#!/usr/bin/env python3

"""
Standalone IMU -> CSV recorder for the Husky A300.

Records the onboard IMU to a .csv file until you press Ctrl+C.
Handy for baseline / stationary captures, or for running the recorder
independently in one terminal while you drive the robot from another.

Robot namespace:
    /a300_00075

Examples:
    python3 husky_imu_recorder.py
    python3 husky_imu_recorder.py --imu-topic /a300_00075/sensors/imu_0/data_raw
    python3 husky_imu_recorder.py --output baseline.csv

Verify the IMU topic first:
    ros2 topic list | grep -i imu
    ros2 topic hz  <that topic>
"""

import csv
import time
import argparse
from datetime import datetime

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu


NAMESPACE = "/a300_00075"
DEFAULT_IMU_TOPIC = f"{NAMESPACE}/sensors/imu_0/data"   # <-- verify this!


class ImuRecorder(Node):

    def __init__(self, imu_topic, output):
        super().__init__("husky_imu_recorder")

        if output is None:
            output = f"imu_{datetime.now():%Y%m%d_%H%M%S}.csv"
        self.output = output

        self.csv_file = open(self.output, "w", newline="")
        self.writer = csv.writer(self.csv_file)
        self.writer.writerow([
            "t_ros", "t_wall",
            "qx", "qy", "qz", "qw",
            "wx", "wy", "wz",
            "ax", "ay", "az",
        ])
        self.n_samples = 0

        self.sub = self.create_subscription(Imu, imu_topic, self.imu_cb, 50)
        self.get_logger().info(f"Recording {imu_topic} -> {self.output}")
        self.get_logger().info("Press Ctrl+C to stop.")

    def imu_cb(self, msg):
        t_ros = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        self.writer.writerow([
            f"{t_ros:.9f}",
            f"{time.time():.9f}",
            msg.orientation.x, msg.orientation.y,
            msg.orientation.z, msg.orientation.w,
            msg.angular_velocity.x, msg.angular_velocity.y, msg.angular_velocity.z,
            msg.linear_acceleration.x, msg.linear_acceleration.y, msg.linear_acceleration.z,
        ])
        self.n_samples += 1
        if self.n_samples % 100 == 0:
            self.csv_file.flush()

    def close(self):
        if not self.csv_file.closed:
            self.csv_file.flush()
            self.csv_file.close()
        self.get_logger().info(
            f"Saved {self.n_samples} IMU samples to {self.output}")


def main():
    rclpy.init()

    parser = argparse.ArgumentParser(
        description="Record Husky A300 IMU to CSV until Ctrl+C.")
    parser.add_argument("--imu-topic", default=DEFAULT_IMU_TOPIC,
                        help=f"IMU topic (default {DEFAULT_IMU_TOPIC})")
    parser.add_argument("--output", default=None,
                        help="output CSV path (default imu_<timestamp>.csv)")
    parsed, _ = parser.parse_known_args()

    node = ImuRecorder(parsed.imu_topic, parsed.output)

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.close()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
