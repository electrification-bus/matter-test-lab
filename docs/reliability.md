# Reliability tests

The [matter-qa](https://github.com/CHIP-Specifications/matter-qa) reliability/stress scripts (`TC_RT_*`) loop commissioning, multi-admin, discovery and reboot against a DUT to surface intermittent faults a single pass never shows. `reliability.yml` installs them into the Test Harness and runs them.

| Case | What it loops | Iterations | Timeout | Extra settings |
|---|---|---|---|---|
| `TC_RT_1_1` | commissioning and decommissioning | 25 | 1800 | none |
| `TC_RT_1_2` | multi-admin: several fabrics, subscriptions, concurrent reads and writes | 10 | 2700 | `open_commissioning_window_timeout` |
| `TC_RT_2_1` | commissionable discovery over DNS-SD, then commission and decommission | 2 | 4500 | onboarding payload |
| `TC_RT_2_2` | operational discovery across DUT reboot, network change and CASE re-establish | 2 | 4500 | `alter_device_network_config` |

The iteration counts and timeouts are the ones the event's own execution document prescribes, not defaults worth inventing. Raise the timeout whenever you raise the iterations; a run cut off by its timeout files as a failure.

They are unlike every other case this repo runs. An ordinary test case talks to a DUT somebody else started; these **own the DUT app's lifecycle**, SSHing in once per iteration to kill the app, wipe its KVS and relaunch it. Almost everything surprising below follows from that one difference.

## You supply matter-qa

`CHIP-Specifications/matter-qa` is a CSA member repository. This repo neither vendors nor clones it. Clone it yourself, check out the branch your event pins, and point `reliability_src` at it:

```yaml
# host_vars/<your-th>.yml, or -e on the command line
reliability_src: "~/src/matter-qa"
```

The copy goes from the control machine to the Pi rather than being cloned there, because the Test Harness has no GitHub credentials of its own.

**If you cannot see `matter-qa` at all, that is expected until you ask.** CSA membership does not by itself grant access to the CSA GitHub organisations; it is granted on request. Email <help@csa-iot.org> with your GitHub username. Do this early, because nothing here can fetch the repository for you.

## Install

```bash
ansible-playbook reliability.yml --tags install
```

This rsyncs your checkout to the TH, runs matter-qa's `install.sh`, waits for the Test Harness API to come back, and asserts that `th-cli` can actually see `TC_RT_1_1`. Re-run it whenever matter-qa changes or the TH's pinned SDK tag moves.

`install.sh` builds its runner image against **whatever SDK tag the TH is currently pinned to**, not a hardcoded one, so the companion image cannot drift from the SDK image after an upgrade. It restarts the backend as its last step, which is why the playbook then polls rather than continuing straight on.

It also prints `th-cli install failed` on a machine where `th-cli` is already installed under `~/.local/bin`, which a non-interactive SSH session does not have on its `PATH`. Harmless; the playbook's own check is what settles it.

## Run

```bash
ansible-playbook reliability.yml --tags run -e reliability_tests=TC_RT_1_1
ansible-playbook dut.yml --tags run          # restore the DUT afterwards
```

**The playbook stops the `matter-dut` unit and does not restart it.** That is deliberate: the framework leaves the app running as it last launched it, and silently restarting the unit underneath a finished run would hide whatever state the run ended in. Restore it before any ordinary test case.

If you leave the unit running, the framework's `_kill_app()` issues a plain `kill` as the SSH user and cannot touch an app the unit started as root. It then starts a second instance and the two fight over one KVS.

## Settings

All in `group_vars/all.yml`, all overridable with `-e`:

| Variable | Default | Notes |
|---|---|---|
| `reliability_src` | *(empty, required)* | your matter-qa checkout on the control machine |
| `reliability_tests` | `TC_RT_1_1` | comma-separated list is fine |
| `reliability_iterations` | `25` | CSA suggests 25 for `TC_RT_1_1` |
| `reliability_timeout` | `1800` | raise it with the iteration count |
| `reliability_app_path` | *(empty)* | empty composes it from the `[dut]` group's own `sdk_dest`/`dut_out_dir`/`dut_app_binary` |
| `reliability_app_args` | `{}` | extra app arguments, as a **mapping** |
| `reliability_matter_xml_root` | `/root/python_testing/data_model/1.7` | data model path **inside the runner container**; `TC_RT_1_2` and `TC_RT_2_1` need it |
| `reliability_setup_payload` | `{}` | `setup_code` / `qr_code`, for cases that recommission rather than reuse (`TC_RT_2_1`) |
| `reliability_test_case_config` | `{}` | per-case settings, keyed by the test name exactly as called |

`reliability_app_args` is a mapping, not the string `dut_app_extra_args` uses, because matter-qa turns every key under `app_config` into a `--<key> <value>` argument verbatim. Hyphenate exactly as the flag is spelled:

```yaml
reliability_app_args:
  enable-key: "000102030405060708090a0b0c0d0e0f"
```

## Four things that cost a failed run each

- **`reliability_tests_arg` is a path inside the runner container.** `install.sh` mounts the vendored checkout at `/matter-qa`, so the host path fails the run instantly with `FileNotFoundError` and no other clue. `reliability_container_config` holds the right one.
- **The DUT must be given as an IP.** The test runs in a container that does not resolve mDNS, so an inventory name like `matterdut.local` produces a run that starts and then cannot reach the device. The playbook reads the DUT's address from its own facts.
- **Numbers have to stay numbers.** A quoted `"{{ x | int }}"` renders to the string `"1"`, and the framework then raises `'str' object cannot be interpreted as an integer` on `number_of_iterations`. The playbook builds each config object as one whole Jinja expression so the native types survive.
- **The framework authenticates to the DUT with a password.** It connects **TH to DUT**, a hop none of the other playbooks make and for which no key is installed, so `ubuntu_password` has to match what the DUT was actually flashed with. `bootstrap-keys.yml` depends on the same value.

## Two ways a run leaves the lab dirty

**The framework orphans the DUT app.** It starts the app itself, as the SSH user and outside systemd, and leaves it running when the run ends. `systemctl stop matter-dut` does not touch that process, so the next launch dies binding port 5540:

```
Failed to initialize TCP transport: OS Error 0x02000062: Address already in use
Server init failed: ... chipDie chipDie chipDie
```

Nothing then advertises, and the symptom reads as a broken device or a mysterious discovery timeout rather than a stale process. `dut.yml --tags run` now kills any instance systemd does not own and asserts 5540 is free before launching, so this self-heals; if you are diagnosing by hand, look for the app running as your SSH user.

Note that the pattern used to kill it must not match the shell doing the killing. `pkill -f chip-electrical-protection-app` matches its own parent's command line and kills it, which surfaces as a task failing with `rc: -15` and no other explanation. The playbook brackets the first character (`[c]hip-...`) so the regex cannot match the literal in its own command line.

**`TC_RT_2_2` rewrites the DUT's network config and does not put it back.** It writes `/etc/netplan/99-static-eth0.yaml` (owned by the SSH user, not root) with `dhcp4: false` and the static address from `alter_device_network_config`, and leaves the file in place when the run ends. Restoring your own `50-cloud-init.yaml` achieves nothing, because the `99-` file sorts later and wins. To recover, reach the Pi at its **new** address and:

```bash
sudo rm -f /etc/netplan/99-static-eth0.yaml
sudo netplan apply          # drops the connection as the address changes back
```

Take a backup before the run anyway, and know which address you expect the Pi to return to. Where the address comes from a DHCP reservation outside the dynamic pool, it comes back deterministically.

**`alter_device_network_config` needs an address nothing else uses.** A DHCP reservation list is not sufficient evidence: statically configured infrastructure (gateways, resolvers) usually has no reservation at all. Confirm with an ARP probe from the DUT's own segment, where `INCOMPLETE` means nothing answered:

```bash
ping -c2 -W1 <candidate> >/dev/null 2>&1; ip neigh show <candidate>
```

## A limitation of TC_RT_2_2 worth knowing before you run it

The framework keeps SSHing to `rpi_hostname` while the test moves the DUT to a different address, so that value has to follow the change. An IP cannot, and the run fails at cleanup with:

```
Failed to kill app: [Errno None] Unable to connect to port 22 on <old address>
```

The execution document's answer is to use the hostname instead. That only works if the runner can resolve it: the stock Test Harness container resolves ordinary DNS but **not** `.local` mDNS, so an mDNS name fails there too, and a name from static DNS points at the old address by definition. The Matter controller itself is unaffected, since it uses its own mDNS implementation and follows the device fine.

## Expected noise

`Value set for analytics key 'current_heap_used' is empty`, once per iteration, when the DUT does not implement Software Diagnostics. The framework reads `SoftwareDiagnostics.CurrentHeapUsed` for its own analytics. Harmless.

`TC_RT_2_1` can segfault mid-execution, [connectedhomeip#72252](https://github.com/project-chip/connectedhomeip/issues/72252).
