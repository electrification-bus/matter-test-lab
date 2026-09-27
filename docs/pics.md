# PICS

A PICS declares, per endpoint, every cluster, feature, attribute, command and event a device implements. You need one long before you need a test event.

- **Developing.** The Test Harness reads it to decide which steps of a test apply. Run without one and PICS-gated steps behave as though the feature is absent, so tests quietly pass having checked less than you think.
- **Certifying.** The PICS is submitted with the device and is what the Authorized Test Lab uses to derive the set of test cases your device must pass. Understate it and you certify less than you built; overstate it and the ATL runs tests your device cannot pass. This is the artifact, not a by-product.
- **At a test event.** Same as certification, plus the organizers aggregate submitted PICS to judge readiness across participants.

In all three cases the PICS is a claim about your device that somebody else acts on, so it is worth deriving rather than typing.

**This repo distributes no PICS XMLs.** The blank templates are CSA member documents, and a filled PICS describes your device. Both are yours to supply; the two scripts here only operate on files you already have. If you do not have access to the templates, that is between you and the [CSA](https://csa-iot.org/).

## Derive it from the device, do not hand-fill it

The Matter SDK ships a generator that reads a live device and fills the templates from what it reports: [`src/tools/PICS-generator`](https://github.com/project-chip/connectedhomeip/tree/master/src/tools/PICS-generator). It is not the official tool, but hand-ticking several hundred items across three endpoints has no way to verify you did not mistype one.

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

### Feature bits above 9 were dropped

Until [connectedhomeip#74427](https://github.com/project-chip/connectedhomeip/pull/74427) lands, `PICSGenerator.py` formats the feature bit index as hex:

```python
featurePicsList.append(f"{clusterPICS}{featureTag}{bitLocation:02x}")
```

PICS feature codes number the bit in decimal, so the two agree only up to bit 9. Bit 20 becomes `F14`, matches nothing in the template, and the feature is left unsupported with no warning. Clusters derived from Alarm Base put their whole feature set at bit 20 and above, so every feature of such a cluster disappears. Change `:02x` to `:02d` before running it.

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
./scripts/pics_dump.py cmp  <template>/Foo.xml <filled>/Foo.xml    # flags differences
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

Validation passing is not the same as the PICS being right. Read the saved TC list and confirm the cases you expect are in it.
