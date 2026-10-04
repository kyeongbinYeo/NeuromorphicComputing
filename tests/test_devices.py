import json
import unittest
from pathlib import Path
from models.devices import FeTFT, MPBTFT
C = json.loads((Path(__file__).resolve().parents[1] / 'configs/demo.json').read_text())
class DeviceChecks(unittest.TestCase):
    def test_retention_and_protocol_end(self):
        d = FeTFT(C['fetft'])
        d.apply_next_protocol_pulse()
        old = d.g
        d.advance(1000)
        self.assertEqual(d.g, old)
        for _ in range(3): d.apply_next_protocol_pulse()
        with self.assertRaises(ValueError): d.apply_next_protocol_pulse()

    def test_double_exponential_and_reset(self):
        import math
        d = MPBTFT(C['mpbtft'])
        d.pulse(4, 0, 100e-6)
        a, b = d.fast, d.slow
        dt = 0.002
        actual = d.advance(dt)
        expected = C['mpbtft']['baseline_A'] + a*math.exp(-dt/C['mpbtft']['tau_fast_s']) + b*math.exp(-dt/C['mpbtft']['tau_slow_s'])
        self.assertAlmostEqual(actual, expected, places=15)
        d.advance(1)
        self.assertAlmostEqual(d.read_current_A(), C['mpbtft']['baseline_A'], places=12)
        d.reset()
        self.assertEqual(d.fast + d.slow, 0)

    def test_tg_suppression_and_saturation(self):
        a, b = MPBTFT(C['mpbtft']), MPBTFT(C['mpbtft'])
        self.assertGreater(a.pulse(4, 0, 100e-6), b.pulse(4, 5, 100e-6))
        for _ in range(1000): a.pulse(4, 0, 100e-6)
        self.assertLessEqual(a.fast+a.slow, C['mpbtft']['capacity_A'])
        with self.assertRaises(ValueError): a.advance(-1)
