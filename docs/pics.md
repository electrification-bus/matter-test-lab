# PICS

A PICS declares, per endpoint, every cluster, feature, attribute, command and event a device implements. Somebody else acts on it, which is why it is worth getting right:

- **The Test Harness** reads it to decide which steps of a test apply. Run without one and PICS-gated steps behave as though the feature is absent, so tests quietly pass having checked less than you think.
- **A test event's organizers** aggregate submitted PICS across participants to judge whether the release under validation has working test coverage.
- **An Authorized Test Lab** derives from it the set of test cases your product must pass. Understate it and you certify less than you built; overstate it and the ATL runs tests your device cannot pass.

## Two jobs, and they are not the same

The word "PICS" covers two tasks that pull in different directions. Being clear which you are doing saves a lot of confusion, and at a test event you are usually doing both at once.

### Proving new cluster support works

You are adding a cluster to the SDK, with the test plan and scripts that go with it, and a reference app to exercise them.

This is what most test event participation looks like, because a test event and a certification ask different questions. A test event asks **does this release hold together?** Certification asks **does my device certify against a release?** Different subject, different activity.

TE1, TE2 and the SVE are sequential milestones in the run-up to a Matter release. Contributors bring the features they have added and establish that the test coverage for them runs and passes, before the release is adopted; the specification is not public yet. Certification comes later, at an Authorized Test Lab, against a version that is already out.

Two different PICS questions live here, and they have different answers:

- **Does my test plan hold together?** Do the codes it references exist, is the conformance self-consistent, does every element have an item? That is a question about the *specification*, and the PICS templates are the spec-derived artifact that answers it. They are generated from the test plan text, which also means they inherit whatever the plan got wrong: the hex-versus-decimal split below arrived exactly that way.
- **What does my reference app actually support?** That is a question about an implementation, and it has to be answered by the implementation. The tests select on it, so a wrong answer means the wrong tests run.

The scripts here are for the second question, and `pics_dump.py gap` connects the two.

#### The reference app should cover the surface the spec adds

For a release cycle the two questions meet. If the reference app implements only part of the new spec surface, the tests for the rest never run, and nobody finds out they are broken until a product implements them after the release is out. So the **specification defines the coverage target** and the app's PICS is the measurement against it; the difference is a finding, not a fact of life.

The blank template is that target, since it enumerates every item the cluster defines. Compare it against what the device reports, across every endpoint that carries the cluster:

```bash
./scripts/pics_dump.py gap <template>/Power\ Topology\ Cluster\ Test\ Plan.xml \
    <filled>/ep1/Power\ Topology\ Cluster\ Test\ Plan.xml \
    <filled>/ep2/Power\ Topology\ Cluster\ Test\ Plan.xml
```

**Triage the output rather than acting on it.** Some entries are unreachable by construction:

- **Choice conformance.** `PWRTL`'s `NODE`, `TREE` and `SET` are all `choice="a"`, so a single endpoint can offer exactly one. Covering all three needs three endpoints, not a bigger feature map.
- **Dependent elements.** `DYPF` requires `SET`, and `AvailableEndpoints` requires `SET`, so skipping one silently removes the others from reach.
- **Disallowed elements.** An element whose conformance is `X` cannot be offered by any conformant server, so it can never appear.
- **Provisional elements**, which a release may deliberately not exercise.

What is left after that triage is the real gap, and it is worth knowing before an event rather than after. Run against the SDK's `electrical-protection-app`, for instance, Power Topology reports `F00`, `F02`, `F03`, `A0000` and `A0001` unsupported: it offers `TREE` on both its endpoints, so nothing it exposes ever exercises the node or set topologies.

### Declaring a product

A finished device going to an ATL, or being run against the full certification suite. Same mechanics as above, higher stakes, and the same answer: the values come from the implementation.

## Why the values come from the device, not the spec

It is tempting to think that for your own reference app you can write the PICS from the design, since you chose what to build. Mostly you cannot.

A specification defines what is *possible* and the conformance closure over it. It cannot tell you what an implementation chose:

| | From the spec? |
|---|---|
| Mandatory given your choices (declare `ADJUST`, and its threshold attributes become mandatory) | yes |
| The choices themselves (does this build offer `ADJUST` at all?) | no |
| Anything conformance marks optional | no |

So even for an app you wrote, the spec gives you a template plus a closure and you still supply every choice, which is most of a PICS.

**A code-driven cluster server makes this worse, and quietly.** In a modern SDK cluster the ZAP configuration only enables the cluster; the attribute, command and feature lists are supplied at runtime by the C++ instance. The SDK's `electrical-protection-app` is a good example: its `.matter` file lists four Electrical Alarm attributes, while the running device serves fourteen, because the feature set is passed in `main.cpp` and the closure is computed from it. Read the design artifact and you understate your own device by ten attributes. Probe it and you get the right answer.

The general rule: the PICS has to describe the binary, because the binary is what the tests run against. Your intent and your build drift.

That is about where the *values* come from. It does not make the binary the standard: in a release cycle the specification is the target, and a reference app that covers less of it than the release adds is a gap to close, not a PICS to declare and move on from. See the gap check above.

### The tooling is already a hybrid

Spec where the device cannot answer, device everywhere else:

- The generator takes `--dm-xml`, the per-release spec scrape, and uses it for **event** conformance, because the device cannot report its event list (the global attribute was removed).
- **TC-IDM-10.4** (`TC_pics_checker.py` in the SDK) verifies a *declared* PICS against the device. The model the ecosystem settled on is declare, then verify. If deriving from the spec were sufficient, that test would have nothing to do.

## Generating one

The Matter SDK ships a generator that reads a live device and fills the templates from what it reports: [`src/tools/PICS-generator`](https://github.com/project-chip/connectedhomeip/tree/master/src/tools/PICS-generator). It is not the official tool, and its output still has to pass the official PICS Tool, but hand-ticking several hundred items across three endpoints has no way to catch a single mistyped one.

```bash
# DUT running and advertising as commissionable
cd <sdk>
source out/python_env/bin/activate
cd src/tools/PICS-generator
python3 PICSGenerator.py \
    --pics-template <blank template folder> \
    --pics-output   <out> \
    --dm-xml        <sdk>/data_model/<release> \
    --commissioning-method on-network --discriminator 3840 --passcode 20202021 \
    --storage-path  <out>/admin_storage.json
```

It commissions the device, walks every endpoint, and writes `GeneratedPICS/endpointN/` plus `Base.xml`. To re-run against a device it has **already** commissioned, drop the commissioning flags and reuse the same `--storage-path`; re-running with them fails discovery, because the device is no longer advertising.

### Feature bits above 9, and two conventions in the wild

The PICS Guidelines spell a feature bit in **hex**: *"Feature bit position `<hh>` (in range [0x00..0x1f])"*, with `DRLK.S.F0b` for bit 11 as the example. `PICSGenerator.py` formats the bit with `:02x` to match, and for Door Lock, Thermostat and Camera AV Stream Management that is right.

Some test plans number theirs in **decimal** instead. `RVCRUNM.S.F20` is bit 20 (`DIRECTMODECH`), and the Electrical Alarm and Electrical Protection Alarm plans do the same. `F20` is outside the `[0x00..0x1f]` range the Guidelines define, so those codes are non-conformant, and the published templates inherit them because the PICS XML is generated from the test plan text.

If your cluster is one of those, the generator emits the hex spelling, matches nothing in the template, and leaves the feature unsupported **with no warning**. Change `:02x` to `:02d` locally to work against it.

Do not carry that patch upstream: it is correct only for the non-conformant clusters and breaks the conformant ones. Emitting both spellings does not work either, since hex bit 20 and decimal bit 14 are both `F14`. Check which convention your own templates use before you trust the output, and verify the generated PICS against the feature map the device actually reports.

### What it cannot fill

Three gaps the tool documents, and a fourth it does not:

1. **`Base.xml` / MCORE** is not derived from the device. Fill it from what you can observe: the app's startup banner for the onboarding payload and commissioning flow, `avahi-browse -rpt _matterc._udp` and `_matter._tcp` on the DUT for the TXT keys and subtypes it really advertises, and the journal for which events it emits.
2. **Events** are marked from spec conformance alone, so an optional event the device does emit comes back false.
3. **Client PICS** are not derived.
4. **PIXITs are untouched**, so each keeps the template's `0x00` placeholder. Not cosmetic: the PICS Tool reads a placeholder as a supplied value, and a PIXIT whose condition your device does not meet then fails validation outright if its status is `O`, or warns if it is `M`. Set the inapplicable ones to `N/A`.

## The two layouts

The same values are needed in two shapes, and neither consumer tolerates the other's:

| Consumer | Shape |
|---|---|
| A test event's data stockpile | one ZIP, `DUT/ep0/*.xml`, `DUT/ep1/*.xml`, ... |
| `th-cli --pics-config-folder` | one **flat** folder per endpoint group, ep0's files plus that endpoint's |

The Test Harness folder has to be flat because `th_cli`'s `read_pics_config` lists it non-recursively and keeps only names ending `.xml`. Hand it a `DUT/epN` tree and it yields zero PICS **with no error**, and every PICS-gated step then behaves as though unsupported.

Two filenames collide when you flatten ep0 and epN together. `Descriptor Cluster Test Plan.xml` should take the endpoint under test, since that is the endpoint the cases run against. `Base.xml` should take ep0's, which is the fully filled one.

Put `Base.xml` in every endpoint folder. Give ep0 the full MCORE fill and the others only the items that apply to every endpoint: that is the SDK's own guidance in [`docs/testing/pics_and_pixit.md`](https://github.com/project-chip/connectedhomeip/blob/master/docs/testing/pics_and_pixit.md), on the grounds that commissioning and discovery tests only need to run against ep0.

## Scripts

### `scripts/pics_dump.py`

Dump or diff the `picsItem` values in any PICS XML. Useful for checking what changed after a tool round trip, or comparing your set against a reference.

```bash
./scripts/pics_dump.py dump "Electrical Alarm Cluster Test Plan.xml"
./scripts/pics_dump.py cmp  <template>/Foo.xml <filled>/Foo.xml     # flags differences
./scripts/pics_dump.py gap  <template>/Foo.xml <filled>/ep*/Foo.xml # coverage gaps
```

### `scripts/run_pics_tool.py`

CSA asks participants to rebuild their PICS in the [beta PICS Tool](https://picstool.csa-iot.org/beta) and submit that tool's output. The tool is one self-contained page with **no login and no server side**, so the step can be driven locally rather than clicked:

```bash
./scripts/run_pics_tool.py --pics-dir <dir with ep0/ ep1/ ep2/> --out <dir>
```

It loads each endpoint, validates, saves the PICS ZIP and the test case list, and exits non-zero on a validation error. Needs [`spel`](https://github.com/Blockether/spel) on `PATH`.

Three things about the tool the script exists to handle, each of which fails quietly by hand:

- **The endpoint folder selector decides the `EPn/` folder in the saved ZIP**, and defaults to 0. Load endpoint 1's files with it left on 0 and they are saved as endpoint 0.
- **`Save TCList` right after a validate can save nothing.** `picstool_savetclist()` checks `tclist.length` before calling the `picstool_update()` that fills it, and that does not happen synchronously.
- **Saves go through `saveAs()`**, so replacing it with a collector is how you get the bytes without fighting browser downloads.

Validation passing is not the same as the PICS being right. Two further checks are worth the minutes:

- **Read the saved TC list** and confirm the cases you expect to run are in it. That is the thing the PICS exists to produce.
- **Run TC-IDM-10.4** (`TC_pics_checker.py` in the SDK), which compares a declared PICS against the device and is meant to be one of the first tests run at certification. It takes `--endpoint` and `--PICS`, pointed at the directory of XMLs for that endpoint.
