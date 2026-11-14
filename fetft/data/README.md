# Data provenance

- `[Source Data]` `fig2f_protocol.csv`: workbook `Analog reservoir computing via ferroelectric_Source data.xlsx`, sheet `Fig.2`, cells `I3:J34`: pulse number and post-pulse conductance in S. Pulse 1 has no measured before state or delta; both fields are blank.
- `[Source Data]` `fig2g_cycles.csv`: same workbook and sheet, cells `L3:M802`, 800 pulse-number/conductance pairs in S. Rows 1–640 correspond to the paper's 20 cycles of 32 pulses. The remaining 160 are recorded separately without assuming why they are present.
- `[Paper/SI]` Fig.2f in the main paper supplies operation, voltage schedule, 10 µs width and fixed read conditions. These columns are aligned to pulse number, not read from the XLSX.
- `[Modeling Decision]` Fig.2g cycle block and within-block index are derived by grouping every 32 recorded points; no additional experimental metadata is inferred.
- Extraction date: 2026-11-14. Method: `python fetft/data/extract_source_data.py`, `openpyxl` read-only, data-only; numeric values checked exactly against the study transcription before writing. Source workbook remains in ignored `references/`.
- Fig.2h has eight retention current traces at VGS=0 V, VDS=0.1 V, unlike Fig.2f conductance at VGS=1 V. It is not used in this runtime model.
