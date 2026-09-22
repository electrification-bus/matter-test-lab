# Changelog

Notable changes to this project. Newest first. Nothing is released yet, so there are no version numbers.

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) loosely and [Semantic Versioning](https://semver.org/spec/v2.0.0.html) once it starts tagging.

## Unreleased

Moving a working lab from one test event's coordinates to the next one's, which had never been exercised end to end. Everything here was found by doing it on real hardware, and each fault presented as something other than its cause.

### Added

- `th_test_parameters` on `th-run.yml`, a dict rendered into the run config's `test_parameters`, which the Test Harness turns into `--<key> <value>` arguments on the test's command line. Without it a run config carries `test_parameters: null` and no test receives an endpoint, which almost every cluster test needs. The failure is not uniform: a test guarded by `@run_if_endpoint_matches` aborts with "The --endpoint flag is required for this test.", while an unguarded one silently falls back to its own `default_endpoint` and fails against whatever is there. A run with no endpoint set can therefore look partly healthy.
- `dut_app_extra_args` on `dut.yml`, appended to the example app's command line after `--discriminator` and `--passcode`. The case that needs it is `--enable-key`: the example apps zero-initialize the test event trigger key, so `GeneralDiagnostics.TestEventTriggersEnabled` reports false and every test that drives a trigger stops at its first check. Some of those tests assert and fail loudly; others mark their remaining steps skipped and return, which the framework records as a **pass**, so the defect can hide behind a green run.
- `th.yml` updates an existing Test Harness instead of reinstalling it, and picks the path itself by looking for a checkout, so the same command is right on a bare Pi and on an installed one. The update path is reachable on its own with `--tags update`. Reinstalling over a working install is not harmless: it redoes the Docker install and the machine configuration and expects a reboot.
- `CHANGELOG.md`, this file.

### Fixed

- A Test Harness update aborted with "Poetry could not be found". pipx installs Poetry into `~/.local/bin`, which a non-interactive SSH session does not have on its `PATH`, and the update's CLI dependency step needs it. Because it failed after the checkout had moved and the containers had been stopped, the harness was left down on the new code. Poetry is now installed ahead of the install-or-update decision, since both paths need it, and both commands export the path.
- A DUT build failed at code generation with a `zap-cli` version check. `activate.sh` reuses an environment that belongs to the SDK commit it was bootstrapped from, so it is stale once the checkout moves. Whether it matches cannot be inferred from whether the clone changed on the current run, because a re-run after a moved checkout sees an unchanged clone and a still-stale environment. The environment is now stamped with the commit it was built from and compared against the checkout, so a mismatch re-bootstraps and a match keeps the fast path.
- The DUT commissionable-readiness probe could not succeed, and reported a healthy DUT as having timed out while its own diagnostic printed the lines it claimed were missing. Three faults stacked: it matched a log string no current SDK emits, which survives only in old certification YAML fixtures; under `pipefail` the `journalctl | grep -q` pipeline reported failure exactly when it matched, because `grep -q` exits on the first hit and `journalctl` then takes SIGPIPE; and both journal reads were unscoped, which is slow on a long-lived unit and lets a previous launch's banner be read as the current one's. It now matches what the SDK actually logs, reads the journal into a variable rather than a pipeline, and scopes every read to the unit's current invocation.

### Documentation

- The README documents both new variables, shows the per-endpoint invocation, and carries troubleshooting entries for the three ways a missing endpoint or enable key presents: an abort, a silent skip, and a pass that tested nothing.
- The README covers moving a lab between event versions, notes that a pinned version may be a branch rather than a tag (in-progress events have pinned branches, and upstream's update script takes a branch name), and carries troubleshooting entries for the two failures above.
