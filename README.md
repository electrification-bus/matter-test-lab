# matter-test-lab

Ansible automation for a Raspberry-Pi-based [Matter](https://csa-iot.org/all-solutions/matter/) certification lab: flash the SD cards, install the [Matter Test Harness](https://github.com/project-chip/certification-tool), optionally build a reference Device Under Test, then run real certification test cases headlessly and collect the logs.

Two audiences, one setting apart: **developers** running certification tests against a device they are building (the default, no CSA membership needed), and **test event participants** who must pin the exact coordinates their event specifies.

It automates the manual steps in the CSA "Matter TE Survival Guide" so that standing up a lab is a few commands rather than an afternoon, and so that doing it again produces the same lab rather than a slightly different one.

## Two use cases

The Test Harness is not only for certification events, and neither is this repo. Upstream describes it as tooling "designed to simplify development, testing, and certification". One setting picks which you are doing.

### Development (the default, no CSA membership required)

You are building a Matter device and want to run **real certification test cases against it as you go**, long before any formal event. This is the default and it needs no configuration at all:

```bash
ansible-playbook th.yml       # installs a published Test Harness release
```

Everything involved is public. The Test Harness repo and all three of its submodules (backend, frontend, cli) are public repositories cloned over HTTPS, and the executable test content comes from the public Matter SDK. **No CSA membership, no credentials, nothing to request.** `th_version` and `sdk_sha` fall back to published defaults.

You do not need a second Pi for this. The Test Harness will test any commissionable Matter device, so the DUT can be your own hardware; `dut.yml` is entirely optional and exists to give you a known-good reference device.

### Test event (`lab_mode: event`)

You are participating in a CSA test event. The two activities ask different questions about different subjects:

| | Question | Subject |
|---|---|---|
| Test event (TE1, TE2, SVE) | does this release hold together? | the release |
| Certification | does my device certify against a release? | the device |

TE1, TE2 and the SVE are sequential milestones in the run-up to a Matter release. Contributors bring the features they have added and establish that the test coverage for them runs and passes, before the release is adopted. Certification comes later, at an Authorized Test Lab, against a version that is already out.

The event pins a specific Test Harness tag and a specific SDK commit and you must use **those exact values**, so in this mode both are required and an unset one fails immediately with an explanation. Defaulting to something else would quietly invalidate your results, so the tool refuses to guess.

```yaml
lab_mode: event
th_version: "..."   # from your test event materials
sdk_sha: "..."      # from the same event
```

Both coordinates are whatever your event's materials say. `th_version` is passed to git as-is, so a branch is as valid as a tag, and in-progress events have so far pinned branches: upstream's own update script documents its argument as a branch name. Do not assume a published tag exists for the version you were given.

| | Development | Event |
|---|---|---|
| CSA membership | not needed | required |
| `th_version` | published default | **you supply** |
| `sdk_sha` | `master` | **you supply** |
| DUT | your device, or the reference app | usually the reference app |
| Hardware | 1 Pi + your device | 2 Pis |

### Getting into the CSA GitHub repositories

Membership alone does not get you in. Access to the CSA GitHub organisations is granted on request rather than automatically: email <help@csa-iot.org> and include your GitHub username.

The one that catches people out is [`CHIP-Specifications/matter-qa`](https://github.com/CHIP-Specifications/matter-qa), which holds the reliability scripts an event may require you to run (see [reliability tests](docs/reliability.md)). The test plans live in the same organisation. Ask early: nothing in this repo can fetch them for you, and the request is not instant.

## What this repo will never ship

Test events pin coordinates and distribute test plans and PICS files to participants. **None of that is in this repo, and none of it will be.** In event mode the two coordinates are empty by design, and PICS are a path you supply (`th_pics_folder`) pointing at a folder you have placed on the Test Harness. The repo helps you *build* and check that folder ([docs/pics.md](docs/pics.md)) without shipping a single PICS XML, and the same applies to the reliability scripts: `reliability.yml` installs a checkout you provide.

If you do not have access to those materials, that is between you and the [CSA](https://csa-iot.org/); this repo will simply tell you what is missing. Nothing the automation *installs* is gated: the Test Harness, the Matter SDK and Ubuntu are all public.

## What you need

Hardware:

- **One or two Raspberry Pis.** One is always the Test Harness. A second becomes the reference DUT, which you only need if you are not supplying your own device. Developed on Pi 5 (8 GB); a Pi 4 with 4 GB or more should also work.
- **A microSD card per Pi, 64 GB or larger**, plus a card reader. The DUT's SDK checkout and build run into tens of GB, so 32 GB is tight there; the Test Harness is less demanding.
- Power for each Pi, and both on the same LAN as your control machine. mDNS (`.local`) must resolve on your network. See [Wired, and what WiFi would take](#wired-and-what-wifi-would-take).

Control machine:

- **macOS** for `flash-pi`, which uses `diskutil`. It needs `xz` and `pv` (`brew install xz pv`); `curl`, `shasum` and `diskutil` are built in. The Ansible playbooks themselves are platform-neutral, so if you flash the cards some other way you can drive them from Linux.
- **Ansible** (a virtualenv or `pipx install ansible` is fine).
- An **SSH keypair**, whose public key path goes in `operator_pubkey`.

### Wired, and what WiFi would take

**This lab is wired Ethernet by design, and that is the only configuration it has been run in.** Nothing here is tested over WiFi. Saying so plainly because discovery is the whole game in Matter testing, and discovery is where a wireless network differs.

Nothing in the playbooks names an interface. Ansible reaches both Pis over SSH by their `.local` names, and the Test Harness and DUT talk over whatever the OS routes, so WiFi ought to work. Three things to expect if you try it:

- **`flash-pi` does not seed WiFi credentials.** It writes cloud-init `user-data` with the hostname and your SSH key only. For a wireless Pi, add a `network-config` file to the boot partition alongside it, or first-boot on Ethernet and configure netplan before unplugging.
- **mDNS depends on multicast, and access points are where multicast goes to die.** Client isolation, multicast-to-unicast conversion and IGMP snooping all break `.local` resolution in ways that look like a broken DUT rather than a broken network. If commissioning finds nothing, test `avahi-browse` before suspecting the device.
- **WiFi power save adds latency and drops.** Matter's discovery and CASE timeouts are not generous. `iw dev wlan0 set power_save off` is worth trying before concluding anything.

One thing gets *better* on WiFi: the hostname quirk in [Troubleshooting](#troubleshooting) disappears, because the SDK's preference for the `wlan0` MAC is then the interface actually carrying traffic.

If you do run this over WiFi, an issue or PR saying what broke would be welcome.

## The workflow

Configure, flash, run. Steps 4 and 5 are optional and depend on what you are doing: a PICS once you move past the tests that need no arguments, and the reliability scripts if your test event asks for them.

### 1. Configure

```bash
git clone https://github.com/electrification-bus/matter-test-lab.git
cd matter-test-lab
source setup-env.sh          # sets ANSIBLE_CONFIG, and forces Apple's ssh on macOS

cp examples/inventory.ini inventory.ini
$EDITOR inventory.ini        # your two hostnames and their MACs
```

For **development** use that is all the configuration there is; skip to step 2.

For a **test event**, put the coordinates where they will not be committed:

```bash
mkdir -p host_vars
cp examples/host_vars/*.yml host_vars/
$EDITOR host_vars/MatterTH.local.yml    # lab_mode + th_version
$EDITOR host_vars/MatterDUT.local.yml   # sdk_sha
```

`inventory.ini` and `host_vars/` are both gitignored, so your hardware details and event coordinates stay local. Everything else is in [`group_vars/`](group_vars/), which is heavily commented.

### 2. Flash the SD cards

`flash-pi` downloads the Ubuntu image once (cached and checksum-verified), lets you pick the target disk safely, and pre-seeds cloud-init so the Pi boots with the right hostname, your SSH key installed, and key-only SSH. There is no `ssh-copy-id` step and no wrong-hostname risk: a flashed Pi comes up ready for Ansible.

```bash
./flash-pi MatterTH      # then swap cards and:
./flash-pi MatterDUT
```

Only *external physical* disks are offered, so your internal drive never appears, and you retype the chosen disk's size to confirm before anything is erased.

Insert each card, power on, wait a minute or two for cloud-init, and the Pi is reachable as `<hostname>.local`. If you flash some other way, install your key afterward with `bootstrap-keys.yml`.

### 3. Run the playbooks

Check you are talking to the right Pis first. This is read-only and takes seconds:

```bash
ansible-playbook th.yml  --tags verify
ansible-playbook dut.yml --tags verify
```

Then install. No `--ask-become-pass` is ever needed, because cloud-init grants `ubuntu` passwordless sudo.

```bash
ansible-playbook th.yml     # Test Harness: 20-40+ min, reboots near the end
ansible-playbook dut.yml    # DUT: 45-90 min first time, idempotent afterwards
```

The same two commands move an existing lab to a new version, which is what a second test event asks for. `th.yml` looks for a checkout and updates it in place rather than reinstalling over a working Test Harness, and `dut.yml` re-bootstraps the build environment when the SDK commit has moved. Neither needs a reflash.

```bash
ansible-playbook th.yml --tags update   # the Test Harness update path on its own
```

Launch the DUT app, then run a test against it and collect the logs:

```bash
ansible-playbook dut.yml --tags run
ansible-playbook th-run.yml -e th_tests=TC-ACL-2.1
```

### 4. Give the tests a PICS

`TC-ACL-2.1` runs without one. Most cluster tests gate individual steps on PICS, and with none supplied they behave as though every feature is absent, so a test can pass having checked almost nothing. If you are bringing up a new cluster, this is also how you show its tests actually select and run; certification is a later, separate activity at an Authorized Test Lab.

Derive it from the running device rather than hand-ticking hundreds of items, then point `th_pics_folder` at it:

```bash
ansible-playbook th-run.yml -e th_tests=TC-FOO-1.1 \
    -e th_pics_folder=/home/ubuntu/pics-ep1 \
    -e '{"th_test_parameters": {"endpoint": "1"}}'
```

The folder is one you place on the Test Harness, and it has to be **flat**: `th-cli` lists it non-recursively and silently yields zero PICS from a nested one. [docs/pics.md](docs/pics.md) covers deriving it with the SDK's generator, the four things that generator cannot fill, the two layouts its consumers need, and the two scripts here for checking the result.

### 5. Reliability tests, if your event asks for them

The matter-qa reliability scripts (`TC_RT_*`) loop commissioning, multi-admin, discovery and reboot to surface intermittent faults a single pass never shows. They are unlike everything above: they **own the DUT app's lifecycle**, restarting it once per iteration, so `reliability.yml` stops the `matter-dut` unit for the duration.

```bash
ansible-playbook reliability.yml --tags install     # once; you supply the matter-qa checkout
ansible-playbook reliability.yml --tags run -e reliability_tests=TC_RT_1_1
ansible-playbook dut.yml --tags run                 # restore the DUT afterwards
```

See [docs/reliability.md](docs/reliability.md).

Most cluster tests need arguments that `TC-ACL-2.1` does not. Pass them with `th_test_parameters`, which becomes the run config's `test_parameters`; the Test Harness turns each key into a `--<key> <value>` argument on the test's command line:

```bash
ansible-playbook th-run.yml -e th_tests=TC-FOO-1.1 \
    -e '{"th_test_parameters": {"endpoint": "1"}}'
```

The endpoint is the one almost every cluster test needs, and omitting it fails in two different ways depending on the test. A run config carries one set of parameters, so group the tests you pass in `th_tests` by the endpoint they run on and make one invocation per group. Take the endpoint from your own device rather than from a script's CI header: those describe the app upstream CI runs the test against, which is usually not yours.

**Each case runs as its own Test Harness run, and its log is fetched as it finishes.** That is deliberate: the Test Harness logs per *run* and offers no per-case export, so batching ten cases into one run produces a single log covering ten cases, and result submission wants a log per result. Pass as many cases as you like in `th_tests`; they are split and run one at a time.

After relaunching the DUT, the first run needs `-e th_commission_first=true`. The DUT's storage was wiped, so the Harness must commission afresh rather than reuse the fabric it remembers:

```bash
ansible-playbook dut.yml --tags run
ansible-playbook th-run.yml -e th_tests=TC-FOO-1.1 -e th_commission_first=true
ansible-playbook th-run.yml -e th_tests=TC-FOO-1.2,TC-FOO-1.3     # reuse is correct now
```

Logs land in `./results/` (gitignored), one run log and one grouped archive per case. How you submit them is defined by your test event; this repo does not encode any submission process.

## The playbooks

| Playbook | What it does | Tags |
|---|---|---|
| `th.yml` | Installs `certification-tool` at your pinned version on a bare Pi, or updates an existing checkout in place; installs `th-cli` and self-heals the backend container. | `verify`, `install`, `update`, `apt`, `ports`, `thcli`, `backend` |
| `dut.yml` | Clones the SDK at your pinned commit, checks out Linux submodules, bootstraps pigweed, builds an example app, and launches it as a commissionable device. | `verify`, `build`, `apt`, `run` |
| `th-run.yml` | Drives `th-cli` over SSH to run a test or list of tests headlessly, then fetches the grouped archive, run log and trace logs. | `run`, `collect` |
| `bootstrap-keys.yml` | Installs your SSH key on a Pi flashed some other way. Not needed after `flash-pi`. | |
| `reliability.yml` | Installs the matter-qa reliability/stress scripts (`TC_RT_*`) into the Test Harness and runs them. You supply the matter-qa checkout. See [docs/reliability.md](docs/reliability.md). | `install`, `run` |

Every playbook starts by asserting it is talking to the intended, correctly-flashed Pi: login user, OS version and release, architecture, hostname, and that the configured MAC actually belongs to that machine. A wrong or stale flash fails in seconds instead of 45 minutes into a build.

## Bringing your own DUT

The Test Harness tests any commissionable Matter device, so `dut.yml` is optional. To test hardware you are building, leave the `[dut]` inventory group empty, skip `dut.yml` entirely, and point the commissioning parameters in `group_vars/all.yml` at your device:

```yaml
dut_pairing_mode: "onnetwork"   # or ble-wifi / ble-thread for a commissioning-over-BLE device
dut_discriminator: "3840"
dut_setup_code: "20202021"
```

Then run tests against it with `th-run.yml`, which only talks to the Test Harness and does not care what the DUT is.

If you do use `dut.yml`, `dut_app_extra_args` appends arguments to the app's command line. The usual need is `--enable-key`, without which any test that drives a TestEventTrigger stops at its first check:

```yaml
dut_app_extra_args: "--enable-key 000102030405060708090a0b0c0d0e0f"
```

The reference DUT that `dut.yml` builds is still worth having. It is a known-good device, which makes it the fastest way to answer "is this failure my device, or my lab?", and it lets you practise the whole loop before your own hardware is ready. Point `dut_example_path` at a different example app, or at your own app in an SDK fork, whenever that is more useful.

## Troubleshooting

- **`ansible-playbook` cannot find the inventory, or "Could not match supplied host pattern".** Either you have not copied `examples/inventory.ini` to `inventory.ini`, or you have `ANSIBLE_CONFIG` exported for another project, which wins over this repo's `ansible.cfg`. Run `source setup-env.sh`.
- **A run fails on `operational discovery ... CHIP Error 0x00000032: Timeout`, or on `Avahi resolve failed`.** The Harness reused a fabric the DUT no longer has, because the DUT was relaunched and its storage wiped. It keeps a commissioning snapshot in `admin_storage.json` and offers to reuse it; reusing it after the DUT's storage was wiped means operational discovery looks for a fabric and node that no longer exist, finds nothing, and times out. **This presents as a network fault and is not one**: the Test Harness host resolves the DUT's records perfectly well at the same moment.

  `-e th_commission_first=true` is meant to decline the reuse, but the prompt feeder is unreliable: two different prompts appear and they do not share an answer, so a single repeated keystroke either reuses a dead fabric or answers FAILED to "Make sure the DUT is in Commissioning Mode" and cancels the run. The deterministic fix is to remove the snapshot so there is nothing to reuse, immediately before the run, because a finished run writes it back:

  ```bash
  ssh <th> 'sudo docker exec certification-tool-backend-1 rm -f /app/admin_storage.json'
  ```

  Confirm from the run log that it says `Commissioning complete ... success` rather than `Copying file /app/admin_storage.json to container`.
- **A test passes having checked nothing.** Most often a missing PICS: `th-cli` needs a *flat* folder of XMLs and silently yields zero PICS from a nested one, after which every PICS-gated step behaves as though the feature is absent. See [docs/pics.md](docs/pics.md).
- **A generated PICS leaves whole features unsupported.** The PICS Guidelines spell a feature bit in hex (`DRLK.S.F0b` is bit 11) and the SDK's generator follows that, but some test plans number theirs in decimal, so the generated item number matches nothing in the template and the feature is dropped without a warning. See [docs/pics.md](docs/pics.md).
- **A reliability run fails immediately with `FileNotFoundError`.** Its settings path is read inside the runner container, not on the Test Harness filesystem. `reliability_container_config` holds the right one. See [docs/reliability.md](docs/reliability.md).
- **apt fails on a freshly flashed Pi, or `-dev` packages conflict.** Both are known quirks of the Pi Ubuntu image and are worked around automatically. See [docs/pi-image-quirks.md](docs/pi-image-quirks.md).
- **Commissioning aborts with a SIGABRT that looks like a crash.** Check `dut_discriminator` is 4095 or less. It is a 12-bit field, and an out-of-range value makes both the app and the controller abort in a way that reads like a device fault.
- **A Test Harness update stops with "Poetry could not be found".** Fixed; update if you are seeing it. pipx installs Poetry into `~/.local/bin`, which a non-interactive SSH session does not have on its `PATH`, and the update's CLI step needs it. It failed after the containers had been stopped, so the symptom was a Test Harness left down on the new code, which looks like a broken install rather than a missing path entry.
- **A DUT build fails code generation with "Version validation failed: required at least ...".** Fixed; update if you are seeing it. The pigweed environment belongs to the SDK commit it was bootstrapped from and carries that commit's `zap-cli`, so it goes stale when the checkout moves. The playbook now stamps the environment with its commit and re-bootstraps on a mismatch.
- **A test aborts with "The --endpoint flag is required for this test."** Pass `th_test_parameters`, for example `-e '{"th_test_parameters": {"endpoint": "1"}}'`. A test guarded by `@run_if_endpoint_matches` fails this way; one without that guard instead falls back to its own `default_endpoint`, usually 0, and fails against the root node as though the device were broken. A run with a missing endpoint can therefore look partly healthy.
- **A test is skipped rather than run, and files as no result.** `@run_if_endpoint_matches` skips when the configured endpoint does not offer the feature the test gates on. Check the endpoint against your device, not against the script's CI header.
- **Tests that drive a TestEventTrigger report a pass without testing anything.** Set `dut_app_extra_args` to pass `--enable-key`. The example apps zero-initialize the key, so `GeneralDiagnostics.TestEventTriggersEnabled` reads false, and a test that checks it then commonly marks its remaining steps skipped and returns, which the framework records as a pass. Some tests assert instead and fail loudly; do not assume a green run means the key was set.
- **The EVSE app aborts at startup with "PowerAdjustment and PowerRangeAdjustment features are mutually exclusive".** Those two DEM features cannot both be set (`examples/energy-management/device-energy-management/src/DeviceEnergyManagementManager.cpp:64`). The Linux EVSE app's default feature map `0x7b` includes PowerAdjustment, so adding PowerRangeAdjustment (`0x80`) to it gives `0xFB` and the app dies on `VerifyOrDie` at `EnergyEvseMain.cpp:305`. Drop PowerAdjustment: `--featureSet=0xFA`. The unit shows as `failed` seconds after the playbook reports the DUT commissionable, because it advertises before `ApplicationInit()` runs.
- **Extra app arguments silently vanish.** `-e dut_app_extra_args="--a=1 --b 2"` loses everything after the first space: Ansible's `key=value` extra-vars form splits on whitespace into separate variables. Use the JSON form, `-e '{"dut_app_extra_args": "--a=1 --b 2"}'`. Check the resulting command line in `journalctl -u matter-dut` rather than assuming.
- **The DUT's Matter hostname names `wlan0`, on an Ethernet-only Pi.** Expected, and not a misconfiguration. On Linux the SDK takes the primary MAC from the interface named by `CHIP_DEVICE_CONFIG_WIFI_STATION_IF_NAME`, default `wlan0`, and matches on the name alone without checking the interface is up or has an address (`src/platform/Linux/ConfigurationManagerImpl.cpp:133`). Every stock Pi has a `wlan0`, so a lab running on Ethernet advertises a hostname one off its `eth0` MAC: `eth0` at `88:a2:9e:1c:cc:36` yields `88A29E1CCC37.local`. Avahi still publishes A records for that name with the real `eth0` address, so resolution works; we could not show any harm. Raised upstream as [connectedhomeip#74524](https://github.com/project-chip/connectedhomeip/issues/74524). Do not chase it when debugging discovery.
- **Debugging discovery at all.** The two views worth having, run on the Test Harness:

  ```bash
  avahi-browse -rt _matterc._udp   # commissionable: present before commissioning
  avahi-browse -rt _matter._tcp    # operational: present only once commissioned
  avahi-resolve -n <HOSTNAME>.local
  ```

  An uncommissioned DUT advertises only the first, which is normal rather than a fault. Other Matter products on the LAN show up in both, so match on the hostname derived from your DUT's MAC rather than assuming a record is yours. A controller-side `Avahi resolve failed` followed by `AddressResolve ... CHIP Error 0x00000032: Timeout` is operational discovery failing, which affects only test cases that force a fresh CASE session; cases riding the session established at commissioning are unaffected, so the failure looks selective.
- **The Test Harness backend exits during install.** Known and self-healed by `--tags backend`. The backend clones the SDK during prestart; if DNS is flaky during the heavy install that clone fails and the container exits. DNS recovers, so a restart re-clones and it comes up.

## Reference

| Path | Purpose |
|---|---|
| `th.yml` / `dut.yml` / `th-run.yml` | The playbooks. |
| `group_vars/all.yml` | Settings shared by both Pis. |
| `group_vars/th.yml` / `dut.yml` | Per-role settings, including the two you must supply. |
| `examples/` | Templates for `inventory.ini` and `host_vars/`, both gitignored in place. |
| `tasks/verify_target.yml` | Shared: assert hostname, MAC and OS image match config. |
| `tasks/apt_prepare.yml` | Shared: work around the Pi image's apt quirks. |
| `flash-pi` | SD card flasher (macOS): cached download, safe disk pick, cloud-init pre-seed. |
| `bootstrap-keys.yml` | Install your SSH key on a Pi flashed another way. |
| `ansible.cfg` / `setup-env.sh` | Connection defaults; source `setup-env.sh` first. |
| `docs/pi-image-quirks.md` | The two Pi Ubuntu image quirks and why they are handled. |
| `docs/pics.md` | Why you need a PICS, deriving one from the device rather than by hand, and the two layouts. |
| `docs/reliability.md` | The `TC_RT_*` reliability tests: install, run, and what fails quietly. |
| `scripts/pics_dump.py` | Dump or diff the values in any PICS XML, or report what a device does not cover of the surface a cluster defines. |
| `scripts/run_pics_tool.py` | Validate a PICS set through the CSA PICS Tool headlessly. |
| `CHANGELOG.md` | What has changed, newest first. |
| `CLAUDE.md` | Shared project context for AI coding agents. |

## Status and contributing

Used to stand up a real lab, in both modes. The Test Harness install tracks a moving upstream, so the development default needs bumping as new releases are published, and an event tag that worked last time may need adjusting for the next one.

See [CONTRIBUTING.md](CONTRIBUTING.md), including when to open a [Discussion](https://github.com/electrification-bus/matter-test-lab/discussions) rather than an [Issue](https://github.com/electrification-bus/matter-test-lab/issues).

Do not send pull requests containing test event materials: tags, SHAs, PICS files, test plans, or logs. Those are yours, not this repo's. See CONTRIBUTING for what that means in practice.

If you want a Matter SDK **development** environment rather than a test lab, see [matter-dev-env](https://github.com/electrification-bus/matter-dev-env), which sets up the repositories, toolchain and build environment on your own machine. The two are companions: build there, test here.

This project is not affiliated with the Connectivity Standards Alliance or the connectedhomeip project. It automates their documented setup rather than replacing it.

## License

Apache-2.0, matching [connectedhomeip](https://github.com/project-chip/connectedhomeip) and [certification-tool](https://github.com/project-chip/certification-tool). See [LICENSE](LICENSE).
