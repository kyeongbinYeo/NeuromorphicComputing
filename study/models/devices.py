"""Educational models. Demo parameters are synthetic, not fitted device data."""
import math

class FeTFT:
    """Replay a calibrated LTP or LTD branch under one fixed pulse protocol.

    Tables include the initial state at index 0. This is not an arbitrary
    pulse-response model: switching branch requires starting a new protocol.
    Current readout assumes a fixed read bias; it is not a transistor I-V model.
    """
    def __init__(self, config):
        self.c = config
        self.reset()

    def reset(self, branch='ltp'):
        if branch not in ('ltp', 'ltd'):
            raise ValueError('branch must be ltp or ltd')
        self.branch, self.index = branch, 0
        self.g = self.c[branch + '_conductance_S'][0]

    def apply_next_protocol_pulse(self):
        table = self.c[self.branch + '_conductance_S']
        if self.index + 1 >= len(table):
            raise ValueError('Protocol exhausted; extrapolation disabled')
        self.index += 1
        self.g = table[self.index]
        return self.g

    def read_current_A(self):
        return self.g * self.c['read_vds_V']

    def advance(self, dt_s):
        if dt_s < 0:
            raise ValueError('dt_s must be nonnegative')
        # First approximation: constant retention; no degradation fitted yet.
        return self.g

class MPBTFT:
    """Two decaying current components at a fixed read bias.

    I(t)=I0+x_fast(t)+x_slow(t). Pulse increments below are a provisional
    saturating rule; only the double-exponential relaxation form is sourced.
    TG affects programming gain here. Direct TG read modulation is not modeled.
    """
    def __init__(self, config):
        self.c = config
        if min(config['tau_fast_s'], config['tau_slow_s'],
               config['reference_width_s'], config['capacity_A']) <= 0:
            raise ValueError('time constants, pulse width and capacity must be positive')
        if not 0 <= config['fast_fraction'] <= 1:
            raise ValueError('fast_fraction must lie in [0,1]')
        self.reset()

    def reset(self):
        self.fast = self.slow = 0.0

    def advance(self, dt_s):
        if dt_s < 0:
            raise ValueError('dt_s must be nonnegative')
        self.fast *= math.exp(-dt_s / self.c['tau_fast_s'])
        self.slow *= math.exp(-dt_s / self.c['tau_slow_s'])
        return self.read_current_A()

    def pulse(self, bg_V, tg_V, width_s):
        if width_s <= 0 or bg_V < 0 or tg_V < 0:
            raise ValueError('Demo supports positive width and nonnegative BG/TG only')
        if abs(bg_V - self.c['reference_bg_V']) > 1e-12:
            raise ValueError('Only reference BG amplitude supported; calibrate other amplitudes')
        # Coarse endpoint pulse update. Pulse-time decay is ignored in this demo.
        gain = math.exp(-self.c['tg_suppression_per_V'] * tg_V)
        occupied = self.fast + self.slow
        headroom = max(0.0, 1.0 - occupied / self.c['capacity_A'])
        delta = min(self.c['capacity_A'] - occupied,
                    self.c['increment_A'] * gain * headroom *
                    width_s / self.c['reference_width_s'])
        a = self.c['fast_fraction']
        self.fast += a * delta
        self.slow += (1 - a) * delta
        return self.read_current_A()

    def read_current_A(self):
        return self.c['baseline_A'] + self.fast + self.slow
