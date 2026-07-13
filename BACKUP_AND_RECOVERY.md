# Backup & Recovery

How to back up the Husky A300 onboard computer, and how to recover it if
something goes wrong. There are two layers, and they cover different failures:

| Layer | Tool | What it captures | When to run |
|-------|------|------------------|-------------|
| Lightweight | `robot_backup.sh` | Config, code, and a manifest of installed software | Often (before/after changes) |
| Full image | Clonezilla | The entire disk, bit-for-bit, bootable | Occasionally (after a known-good setup) |

The lightweight backup lets you **rebuild** a robot. The full image lets you
**clone** one back exactly. Use both.

---

## Layer 1 — Config/data backup (`robot_backup.sh`)

Runs on the robot over SSH and writes a single timestamped, compressed,
checksummed `.tar.gz` onto a USB stick.

### What it includes

- `/etc/clearpath` — Clearpath robot configuration (the important one)
- `/etc/systemd/system` — custom services (e.g. `clearpath-robot`)
- `/etc/netplan` — network configuration
- `/etc/udev/rules.d` — sensor/device rules
- `/home/robot` — user home: scripts, workspaces, etc.
- A `manifest/` folder with `apt_packages.txt`, `pip_freeze.txt`,
  `ros2_packages.txt`, and `system_info.txt` — the record of what software was
  installed, so the environment can be recreated.

Regenerable/bulky items are excluded (colcon `build`/`install`/`log`, caches,
`__pycache__`, ROS bags, recorded `imu_*.csv`).

> Verify the source paths exist on your robot before trusting a backup:
> `ls -d /etc/clearpath /home/robot` — edit the `SOURCES` list at the top of the
> script if anything differs or if you keep a workspace in a non-standard place.

### Running it

1. Plug the USB stick into the robot and SSH in.
2. Mount the stick (it does **not** auto-mount on a headless machine):

   ```bash
   lsblk                              # find the device, e.g. sda1
   sudo mkdir -p /mnt/usb
   sudo mount /dev/sda1 /mnt/usb      # use YOUR device name
   ```

   If it auto-mounted, it'll be under `/media/robot/<LABEL>` — set `USB_MOUNT`
   at the top of the script to that path and skip the manual mount.

3. Run the script:

   ```bash
   chmod +x robot_backup.sh
   ./robot_backup.sh                  # prompts for the sudo password
   ```

   It refuses to run if nothing is mounted at `USB_MOUNT`, so it can't
   accidentally fill the robot's internal disk.

4. Eject safely before removing the stick:

   ```bash
   sync && sudo umount /mnt/usb
   ```

### USB filesystem note

If the stick is **FAT32**, single files are capped at 4 GB — a large backup will
fail. File permissions are stored inside the tarball, so FAT32 is otherwise fine,
but if `/home/robot` is large, format the stick as **exFAT** or **ext4**. Check
the current format with `lsblk -f`.

### Restoring from a tarball

Do **not** blindly extract over `/` on a running system. Instead:

```bash
# inspect what's inside first
tar -tzf <backup>.tar.gz | less

# extract to a staging folder and copy files back deliberately
mkdir restore
tar -xzf <backup>.tar.gz -C restore
# then review restore/etc/clearpath, restore/home/robot, etc. and copy
# the pieces you need back into place
```

Reinstall software using the manifests:

- `apt_packages.txt` — reinstall with `sudo dpkg --set-selections < apt_packages.txt`
  then `sudo apt-get dselect-upgrade` (or install key packages by hand).
- `pip_freeze.txt` — `pip3 install -r pip_freeze.txt`.
- `ros2_packages.txt` — reference list of the ROS packages that were present.

---

## Layer 2 — Full disk image (Clonezilla)

`robot_backup.sh` does not capture a bootable copy of the OS. For true
bare-metal recovery — a dead drive, a corrupted system, a bad update — take a
full disk image occasionally, ideally right after the robot is set up and
known-good.

Clonezilla is the standard free tool for this. The process, at a high level:

1. Put Clonezilla on a boot USB (made from any PC).
2. Shut down the robot and boot it from the Clonezilla USB. Imaging is done
   **offline** (system not running) so the copy is clean and consistent.
3. Choose device → image, and save the image to a second USB drive or external
   disk large enough to hold it.
4. Label the image with the date and store it safely.

To recover, boot Clonezilla again and restore the image back onto the drive.

Because this is done from a boot USB, it needs physical access to the robot and a
few minutes of downtime — which is why it's the occasional layer, not the daily
one.

---

## Recommended practice

- Run `robot_backup.sh` before and after any significant change (new config, new
  packages, workspace changes).
- Keep the USB stick's backups, but also **copy a tarball off the stick** to
  another machine now and then — a stick that lives on the robot isn't off-site
  protection.
- Take a fresh Clonezilla image after any major reconfiguration you'd hate to
  redo by hand.
- Keep at least the last couple of backups, not just the newest, in case a
  problem isn't noticed immediately.
