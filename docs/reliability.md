# Reliability tests

The [matter-qa](https://github.com/CHIP-Specifications/matter-qa) reliability/stress scripts (`TC_RT_*`) loop commissioning, multi-admin, discovery and reboot against a DUT to surface intermittent faults a single pass never shows. `reliability.yml` installs them into the Test Harness and runs them.

| Case | What it loops |
|---|---|
| `TC_RT_1_1` | commissioning and decommissioning |
| `TC_RT_1_2` | multi-admin: several fabrics, subscriptions, concurrent reads and writes |
| `TC_RT_2_1` | commissionable discovery over DNS-SD, then commission and decommission |
| `TC_RT_2_2` | operational discovery across DUT reboot, network change and CASE re-establish |

They are unlike every other case this repo runs. An ordinary test case talks to a DUT somebody else started; these **own the DUT app's lifecycle**, SSHing in once per iteration to kill the app, wipe its KVS and relaunch it. Almost everything surprising below follows from that one difference.

## You supply matter-qa

`CHIP-Specifications/matter-qa` is a CSA member repository. This repo neither vendors nor clones it. Clone it yourself, check out the branch your event pins, and point `reliability_src` at it:

```yaml
# host_vars/<your-th>.yml, or -e on the command line
reliability_src: "~/src/matter-qa"
```

The copy goes from the control machine to the Pi rather than being cloned there, because the Test Harness has no GitHub credentials of its own.

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

## Expected noise

`Value set for analytics key 'current_heap_used' is empty`, once per iteration, when the DUT does not implement Software Diagnostics. The framework reads `SoftwareDiagnostics.CurrentHeapUsed` for its own analytics. Harmless.

`TC_RT_2_1` can segfault mid-execution, [connectedhomeip#72252](https://github.com/project-chip/connectedhomeip/issues/72252).
