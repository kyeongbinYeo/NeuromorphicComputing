# FeTFT v1: measured protocol replay

FeTFT v1 is an empirical device-level Model R for a neuromorphic system, not a
compact or SPICE transistor model. It replays the measured Fig.2f voltage-ramp
protocol; its position is protocol bookkeeping, not a physical latent state.

## Evidence and scope

- `[Source Data]` 32 measured post-pulse conductances were extracted from
  `Fig.2!I3:J34`. The first pre-pulse state is absent. The original workbook
  and all three PDFs remain in the ignored root `references/` directory.
- `[Paper/SI]` PGM pulses 1–16 ramp from +3.50 V to +4.10 V by +0.04 V;
  ERS 17–32 ramp from −4.35 V to −5.10 V by −0.05 V. Each is 10 µs.
  Read is VGS=1 V, VDS=0.1 V. Voltage schedule and read conditions come
  from the paper, not workbook columns.
- `[Modeling Decision]` `initialize()` returns to a pre-protocol cursor with
  **unavailable** conductance. The first application returns the measured
  post-pulse-1 state. No pulse-zero conductance or first delta is invented.

```python
from fetft import FeTFT

d = FeTFT()
event = d.apply_next_protocol_pulse()  # pulse 1, before and delta are None
g_siemens = d.read_conductance()       # pure query
i_amperes = d.read_current()          # G * 0.1 V, at the specified read bias
```

Each returned immutable event contains pulse number, operation, voltage, width,
before/after conductance, delta, and read biases. `protocol_position` counts
completed pulses and `last_event` is None before pulse 1. Reading before pulse 1
raises `StateUnavailableError`. A 33rd pulse raises `ProtocolExhaustedError`;
`initialize()` starts the replay again. There is no arbitrary reset/index API.

Model R is **not** an arbitrary fixed-voltage PGM/ERS model, arbitrary reversal
model, voltage-aware predictive model, retention model, or cycle/device noise
model. `read_current()` is not an arbitrary-bias I-V model. Replay validation
is a data fidelity check, not independent predictive performance.

## Data and validation

See [data/README.md](data/README.md) for extraction and provenance. Run from
the repository root:

```text
python fetft/data/extract_source_data.py
python fetft/validation/validate_fig2f.py
python fetft/validation/analyze_fig2g_variability.py
python -m pytest fetft/tests -q
```

Extraction and optional original-workbook validation require `openpyxl`.
Fig.2g is a cycle-to-cycle reference, not fitting data: the paper shows 20
cycles (640 points); XLSX contains 800. The extra 160 points are retained but
excluded from the 20-cycle statistics and their origin is not inferred. The
first Fig.2g cycle is identical to Fig.2f and is not an independent hold-out.

Fig.2h contains eight retention traces, read at VGS=0 V and VDS=0.1 V. Fig.2f
uses VGS=1 V, so the Fig.2h current is not directly applied to the runtime
conductance. Retention is a future separate extension, not part of Model R.
