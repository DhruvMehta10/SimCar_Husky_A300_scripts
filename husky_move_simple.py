#!/usr/bin/env python3

"""
Drive the Husky A300 forward a set distance at a set speed, using odometry.
Edit SPEED and DISTANCE below, then run:

    python3 husky_move_simple.py
"""

import math
import rclpy
from rclpy.node import Node

from geometry_msgs.msg import TwistStamped
from nav_msgs.msg import Odometry


# ---- edit these two ----
SPEED = 0.15       # m/s
DISTANCE = 1.0     # metres
# ------------------------

TOL = 0.02         # 2 cm tolerance

CMD_TOPIC = "/a300_00075/cmd_vel"
ODOM_TOPIC = "/a300_00075/platform/odom"


class Move(Node):

    def __init__(self):
        super().__init__("husky_move_simple")

        self.pub = self.create_publisher(TwistStamped, CMD_TOPIC, 10)
        self.sub = self.create_subscription(Odometry, ODOM_TOPIC, self.odom_cb, 10)

        self.start_x = None
        self.start_y = None
        self.done = False

        self.get_logger().info(f"Driving {DISTANCE} m at {SPEED} m/s")
        self.get_logger().info("Waiting for odometry...")

    def odom_cb(self, msg):
        if self.done:
            return

        cx = msg.pose.pose.position.x
        cy = msg.pose.pose.position.y

        # latch start pose on first message
        if self.start_x is None:
            self.start_x = cx
            self.start_y = cy
            self.move(SPEED)
            return

        dist = math.hypot(cx - self.start_x, cy - self.start_y)

        if dist >= DISTANCE - TOL:
            self.move(0.0)
            self.done = True
            self.get_logger().info(f"Reached {dist:.3f} m — stopped")
            raise SystemExit
        else:
            self.move(SPEED)

    def move(self, speed):
        msg = TwistStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "base_link"
        msg.twist.linear.x = speed
        msg.twist.angular.z = 0.0
        self.pub.publish(msg)


def main():
    rclpy.init()
    node = Move()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        node.move(0.0)          # final stop
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
