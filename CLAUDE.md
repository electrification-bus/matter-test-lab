# Guidance for AI coding agents

Shared, project-specific context for Claude Code and similar tools. It is checked in deliberately, because everything here is useful to anyone working on this repo and most of it is not inferable from the code alone.

**Keep personal preferences out of this file.** Put those in `CLAUDE.local.md`, which is gitignored, or in your user-level `~/.claude/CLAUDE.md`. This file is for facts about the project, not about you.

## What this is

Ansible that stands up a Raspberry-Pi-based Matter certification lab: flash the SD cards, install the Test Harness (`project-chip/certification-tool`), optionally build a reference DUT from the Matter SDK on a second Pi, then run real certification test cases headlessly and collect logs.

Read `README.md` for the workflow and `group_vars/` for every setting. This file only covers how to work on the code.

## Two modes, and why the code is shaped this way

`lab_mode` (in `group_vars/all.yml`) is the central abstraction:

- `development` (default): everything used is public. The Test Harness repo and all three submodules are public and cloned over HTTPS, and test content comes from the public SDK. No CSA membership, no credentials. `th_version_development` and `sdk_version_development` supply working defaults so a bare run works.
- `event`: a CSA test event pins exact coordinates and the tool must not guess. `th_version` and `sdk_sha` are required, and unset ones fail before any work happens.

The resolution lives in `th_version_effective` and `sdk_version_effective`. **Playbooks read those, never `th_version` or `sdk_sha` directly**, so mode handling stays in one place.

Also note the DUT is optional. The Test Harness tests any commissionable device, so `dut.yml` exists to provide a known-good reference DUT; a developer testing their own hardware skips it entirely and `th-run.yml` still works, because it only talks to the Test Harness.

## The rule that must not be broken

**No test event materials in this repository. Ever.**

That means no Test Harness tags or SDK commits pinned by a specific event, no PICS files, no test plans, no test logs or result archives. Those are distributed to CSA members under membership terms and are not ours to publish.

In `event` mode both coordinates are empty by design, with an assertion that explains where the user gets them. If you are adding something a test event supplies, follow that pattern. **Never commit a working value, even a stale one from a past event**, and never "helpfully" fill in an empty default to make an event-mode run succeed. Failing with a clear message is the correct behavior, not a bug to fix.

The development-mode defaults are a different thing and are fine: `th_version_development` points at a **published** upstream release, not at anything event-gated. Bump it as upstream publishes new ones. It is pinned rather than resolved at runtime on purpose, so two people running this get the same Test Harness.

`results/`, `inventory.ini` and `host_vars/` are gitignored because they accumulate exactly this material. Do not propose tracking them.

## Running anything

Two traps, both of which make the playbooks appear broken:

1. **There is no `inventory.ini` in a fresh clone.** It is gitignored; the template is `examples/inventory.ini`. Without it you get "Could not match supplied host pattern".
2. **`ANSIBLE_CONFIG` exported for another project wins** over this repo's `ansible.cfg`, with the same symptom.

Both are handled by:

```bash
source setup-env.sh
cp examples/inventory.ini inventory.ini   # first time only
```

Useful invocations:

```bash
ansible-playbook th.yml  --tags verify    # read-only, seconds, safe
ansible-playbook dut.yml --tags verify
ansible-playbook th.yml  --check          # dry run
```

## Quality gates

```bash
ansible-lint                                # must be clean
ansible-playbook th.yml     --syntax-check
ansible-playbook dut.yml    --syntax-check
ansible-playbook th-run.yml --syntax-check
markdownlint-cli2 '**/*.md'                 # if docs changed
```

`ansible-lint` conventions that trip agents up:

- **Jinja may appear only at the END of a task `name:`**. `name[template]`.
- **Shell tasks with pipes need `set -euo pipefail`**. `risky-shell-pipe`.
- **Commands need `changed_when`**; use `changed_when: false` for probes. `no-changed-when`.
- Prefer modules over `command`/`shell`, and where a command is genuinely required add `# noqa: command-instead-of-module` with a comment saying why.

## Testing conventions

Most work cannot be fully tested without two Pis. Be honest about that rather than implying coverage.

- `--syntax-check` and `ansible-lint` always.
- `--tags verify` is the cheap real test: read-only, seconds, and it exercises fact gathering plus every assertion.
- `--check` gives a dry run of the longer playbooks.
- When reporting a real run, state the Pi model, the Ubuntu point release, and the Test Harness tag. Without those, "it worked" is not reproducible.

**Never paste test logs into an issue, PR, or commit** while debugging. Use the Ansible task failure instead, and redact hostnames and MACs.

## Things that cost real time to learn

Encoded in the code and worth preserving:

- **The discriminator is a 12-bit field and must be <= 4095.** An out-of-range value makes both the DUT app and the controller `VerifyOrDie`-abort during commissioning with a SIGABRT that reads like a crash rather than a config error.
- **The TH and DUT must come from the same test event.** A mismatched `th_version` and `sdk_sha` produces failures that look like device bugs.
- **The Test Harness backend can exit during install.** It clones the SDK during prestart; flaky DNS under install load kills the clone and the container exits. DNS recovers, so `--tags backend` restarts it and waits for the API. This is self-healing on purpose, not a workaround to remove.
- **The Pi Ubuntu image has two apt quirks**, both handled in `tasks/apt_prepare.yml`. See `docs/pi-image-quirks.md` rather than rediscovering them.
- **`verify_target.yml` asserts hostname, MAC, OS and architecture** before any expensive work, so a wrong or stale flash fails in seconds. Do not weaken it for convenience.

## Layout

| Path | Role |
|---|---|
| `th.yml` | Test Harness install. |
| `dut.yml` | DUT build and launch. |
| `th-run.yml` | Run tests via `th-cli`, fetch logs. |
| `bootstrap-keys.yml` | Key onboarding for a Pi flashed another way. |
| `flash-pi` | macOS SD card flasher with cloud-init pre-seed. |
| `group_vars/` | All settings; `th.yml` and `dut.yml` hold the two you must supply. |
| `examples/` | Templates for the gitignored `inventory.ini` and `host_vars/`. |
| `tasks/` | Shared task files imported by the playbooks. |
| `docs/` | Long-form explanations kept out of the README. |

## Related

`matter-dev-env` (same org) sets up a Matter SDK **development** environment on a workstation. Shared conventions, different audience and different hardware assumptions. Cross-repo changes should keep the conventions aligned but the repos independent; deliberately duplicating a small task file is preferred over introducing cross-repo role sharing.
