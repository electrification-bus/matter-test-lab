# Two quirks of the Raspberry Pi Ubuntu image

Both of these surfaced while automating a real lab, both look like your fault when they happen, and both are handled automatically by `tasks/apt_prepare.yml`. This page exists so that when you see the symptom you can recognise it rather than debug it.

If you are not seeing an apt failure, you do not need this page.

## 1. First-boot apt lock

**Symptom.** Any apt operation in the first few minutes after a fresh boot fails to acquire the dpkg lock. This hits your own tasks and, more confusingly, hits vendor install scripts that shell out to apt themselves, so the error surfaces from inside someone else's script.

**Cause.** The Ubuntu image runs `apt-daily.timer` and `apt-daily-upgrade.timer` on boot, and `unattended-upgrades` holds the dpkg lock while it works. On a Pi that takes minutes, not seconds.

**Handling.** `apt_prepare.yml` stops both timers, then polls until `/var/lib/dpkg/lock-frontend`, `/var/lib/apt/lists/lock` and `/var/cache/apt/archives/lock` are all free, waiting up to ten minutes before giving up with a clear message. Waiting is friendlier than racing, and far friendlier than a lock error from three layers down.

## 2. Missing apt pockets

**Symptom.** A `-dev` package refuses to install because it wants an exact runtime version that is older than what is on the system. For example `libdbus-1-dev` wants `libdbus-1-3 =X` while `X.1` is installed.

**Cause.** The Pi image enables only the base and `-security` apt pockets. Security updates therefore bump the runtime libraries, but the matching updated `-dev` packages live in `-updates`, which is not enabled. The two drift apart and the dependency becomes unsatisfiable.

**Handling.** `apt_prepare.yml` adds `<release>-updates` and `<release>-backports` to `/etc/apt/sources.list.d/ubuntu.sources` before installing anything, which brings the `-dev` packages back in line with the runtime.

## Why not just use a different image

The Test Harness install expects Ubuntu Server on arm64, and `verify_target.yml` asserts the running system matches `expected_ubuntu_version`, `expected_ubuntu_release` and `expected_architecture` so a wrong or stale flash fails in seconds. Both quirks are cheap to work around and stable across point releases, which is preferable to maintaining a custom image.

To move to a newer point release, change `ubuntu_image_url` in `group_vars/all.yml`. Any 24.04.x is fine; the download is verified against the `SHA256SUMS` published alongside it, so no hash is pinned in this repo.
