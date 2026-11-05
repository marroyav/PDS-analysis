# PDS-analysis

Small offline tools for DAPHNE DAQ waveforms and LED calibration.
The code prepares fingerplots and records baseline, noise, clipping and timing
checks. It has no hardware-control operations.

Use the existing campaign environment with NumPy. ROOT is needed for fitting;
PyROOT and SciPy are not required.

```bash
export PYTHONPATH="$PWD/src:$PYTHONPATH"
python3 -m unittest discover -s tests -v
```

## Import the existing scan metadata

Read a scan wrapper JSONL journal, or one `step-*.json` receipt:

```bash
python3 -m pds_analysis.cli import-scan scan.jsonl results/imported
```

Only `step_complete` events are imported from a journal. The importer checks the
extracted `.bin` hash, frame geometry, tags, per-channel counts and common events.
It preserves the original receipt, including settings, LED configuration and
HDF5 provenance, beside and inside each decoded NPZ. Use `--data-dir` if the
extracted files moved from their recorded location. It reuses the wrapper's
HDF5 selection; it does not read raw HDF5 files itself. The analysis report and
fitting provenance retain this receipt. No new acquisition logging is introduced.

## Prepare a fingerplot

First extract accepted, deduplicated frames from stable DAQ intervals. Check
HDF5 fragment status and source mapping in the campaign exporter.

```bash
python3 -m pds_analysis.cli decode frames.bin decoded.npz
python3 -m pds_analysis.cli fingerplot decoded.npz --channel 2 \
  --baseline 0:32 --signal 112:176 --polarity positive \
  --expected-step 1280 --count 10000 --output results/point-001
```

The windows and timestamp step are examples. Choose them from measured timing.
Window ends are exclusive. Charge units are ADC sample sums. The decoder expects
512-byte Ethernet frames containing 256 unsigned 14-bit samples. Channel IDs
and sender stream IDs stay separate. Continuation frames are decoded but are
not yet assembled into long traces.

NPZ input can also use campaign arrays shaped event × channel × sample,
with channel and timestamp vectors. Output contains charge samples, histogram
CSV, mean waveform, analysis settings, input hash and quality checks. A prepared
histogram does not establish a valid SPE fit or LED sweet spot.

## Fit with Henrique Souza's model

Keep [hvsouza/apc_root](https://github.com/hvsouza/apc_root) in a separate checkout.
The adapter uses its pedestal/SPE/2PE model at the revision in references.json.
Supply initial peak locations in the exported charge units:

```bash
python3 -m pds_analysis.apc results/point-001/charges.txt \
  --apc-root /path/to/apc_root --pedestal 0 --spe 100 --twope 200 \
  --output results/point-001-fit
```

It saves a PNG, ROOT histogram and fit, fit status and provenance. Invalid fits
fail. Higher-occupancy spectra may need a wider multi-PE model. This adapter
uses the upstream model, not its full interactive calibration workflow.

## Export for Federico Galizzi's analysis

[fgalizzi/pds-ana](https://github.com/fgalizzi/pds-ana) provides LED analysis,
SNR and noise-spectrum routines. Export decoded raw waveforms for its
`CompleteWF_Binary` reader:

```bash
python3 -m pds_analysis.fgalizzi decoded.npz --channel 2 --count 10000 \
  --expected-step 1280 --output results/point-001-export
```

Upstream, use `data_format="daphne"`, with `n_wf` and `memorydepth` from the
exported metadata. Set baseline and integration windows from the actual data.
The file contains decoded doubles, not DAQ frame bytes. The export is tested;
the full upstream class integration is not yet qualified. Its November 2025
1024-sample configurations must not be applied directly to 256-sample frames.

The scope excludes undershoot correction, deconvolution and pulse-tail recovery.
Raw data and generated results stay outside Git. references.json pins upstream
sources. Nine unit tests cover decoding, observables, timing checks and export.
The optional `tests/root_smoke.py OUTPUT APC_CHECKOUT` checks fitting with
synthetic charges. On CERN ROOT 6.38.00 it recovered separation 99.69 for an
injected 100; this is a software check, not a detector measurement.
