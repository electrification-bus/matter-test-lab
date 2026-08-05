# Contributing

Thanks for your interest in contributing. `matter-test-lab` automates standing up a Raspberry-Pi-based [Matter](https://csa-iot.org/all-solutions/matter/) certification lab: flashing the SD cards, installing the Test Harness, optionally building a reference DUT, and running real certification test cases headlessly.

It serves two audiences: developers testing a device they are building (the default, no CSA membership required) and CSA test event participants. Changes should keep both working, and in particular must not make the development path require credentials.

## Before anything else: do not contribute test event materials

This is the one hard rule, and it is why the repo is structured the way it is.

**Never open a pull request, issue, or discussion containing:**

- Test Harness tags or SDK commits pinned by a specific test event
- PICS files, test plans, or test case content
- Test run logs, result archives, or trace logs
- Anything else distributed to test event participants under CSA membership

Those materials are not ours to publish, and the value of this repo depends on it staying that way. Every access-gated value here is a variable with no default and a message explaining that you supply it. If you find something that is *not* parameterized and should be, that is a bug worth reporting, and please describe it without pasting the material itself.

Logs are especially easy to include by accident when reporting a failure. `results/` is gitignored for exactly that reason. When you need to show output, paste the Ansible task failure, not the test log, and redact hostnames and MACs.

## How to contribute

### Discussions

Use [Discussions](https://github.com/electrification-bus/matter-test-lab/discussions) for:

- Whether something belongs here at all, given the rule above
- Test Harness upstream changes that break the install, and how best to track them
- Running the lab on other hardware (a Pi 4, a NUC, a VM, a single machine) before writing it
- Anything about Matter lab setup, in either mode, even if it does not turn out to be a change here. Shared debugging is much of the point.

Discussions are open-ended and a good place to align before something becomes a concrete change. Aligned outcomes often turn into Issues or pull requests.

### Issues

Use [Issues](https://github.com/electrification-bus/matter-test-lab/issues) for actionable changes:

- A playbook failing, with the failing task and its output (not the test logs)
- Upstream drift: `certification-tool` moved a script, renamed a container, changed its install flow
- A Pi image quirk that should be handled automatically
- Documentation that is wrong or missing a step
- Discussion outcomes with alignment and clear scope

If you are unsure whether something is an Issue or a Discussion, start with a Discussion. We can convert it later.

### Pull requests

Pull requests are welcome.

- Small fixes (a corrected path, a clearer failure message, a package that turned out to be needed) can go straight to a PR.
- Substantive changes (new playbooks, new supported hardware, changes to how coordinates are supplied) are worth a Discussion or Issue first.
- **Keep access-gated values unset.** If you add something a test event supplies, give it an empty default and an assertion that explains where to get it, following `th_version` and `sdk_sha`. Never commit a working value, even a stale one from a past event.
- **Fail fast and explain.** The expensive failures here are the ones discovered 45 minutes into a build. Prefer an assertion up front over an error later, and make the message name the fix.
- **Cite upstream for anything copied.** Package lists, script paths and install flows should say in a comment where they came from, so the next person can check whether upstream moved.
- **Comment the why, not the what.** Heavier comments than typical Ansible are wanted, but only for non-obvious reasons: a hidden constraint, an upstream quirk, why a check exists. Do not restate the task name.
- One commit per logical change is fine. We do not require squash or any particular branch naming.

## Quality gates

Run before opening a PR:

```bash
source setup-env.sh
ansible-lint                                # must be clean
ansible-playbook th.yml     --syntax-check
ansible-playbook dut.yml    --syntax-check
ansible-playbook th-run.yml --syntax-check
markdownlint-cli2 '**/*.md'                 # if docs changed
```

If you must add a `# noqa`, put a comment above the task explaining why the rule genuinely does not apply. Do not silence a rule to make a diff pass.

## Testing

The honest unit of test here is real hardware, and most contributors will not have a spare pair of Pis. Do what you can and say what you did:

- **Always**: `--syntax-check` on all three playbooks, and `ansible-lint` clean.
- **Cheap and valuable**: `--tags verify` against a Pi. It is read-only, takes seconds, and exercises the fact-gathering and assertion paths that most changes touch.
- **`--check`** gives a dry run of the fuller playbooks without changing anything, which catches a surprising number of mistakes.
- **Full runs**: say which Pi model, which Ubuntu point release, and which Test Harness tag you used. "Worked for me" is much more useful with those three facts attached.

State plainly in the PR what you ran and what you did not. An untested path honestly labelled is far better than an implied claim.

## Code of conduct

Be respectful and constructive. We appreciate everyone who takes the time to file an issue, start a discussion, or send a pull request.

## License

By contributing you agree that your contributions are licensed under the [Apache-2.0 License](LICENSE) that covers this project.
