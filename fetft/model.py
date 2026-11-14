"""FeTFT Model R: replay measured post-pulse states, no predictive dynamics."""
from __future__ import annotations

from .parameters import load_protocol


class StateUnavailableError(ValueError):
    """The conductance before pulse 1 was not measured."""


class ProtocolExhaustedError(ValueError):
    """The measured 32-pulse protocol has ended."""


class FeTFT:
    """Replay only the Fig.2f pulse schedule at its fixed read bias.

    The position is a protocol cursor, not a physical latent state. After
    initialize there is no observed conductance until pulse 1 is applied.
    """
    def __init__(self):
        self._steps, self._metadata = load_protocol()
        self.initialize()

    def initialize(self):
        """Reset the replay cursor; do not invent a pre-pulse conductance."""
        self._position = 0

    @property
    def protocol_position(self):
        """Number of completed pulses, 0 through 32."""
        return self._position

    @property
    def last_event(self):
        return self._steps[self._position - 1] if self._position else None

    def read_conductance(self):
        """Pure read of G (S) under Fig.2f read conditions."""
        if self._position == 0:
            raise StateUnavailableError("Conductance before pulse 1 is not available in Fig.2f.")
        return self.last_event.conductance_after_S

    def read_current(self):
        """Pure current (A) at fixed VGS=1 V, VDS=0.1 V; not an I-V model."""
        return self.read_conductance() * self._metadata['read_vds_V']

    def apply_next_protocol_pulse(self):
        """Advance exactly one step and return its immutable measured event."""
        if self._position == len(self._steps):
            raise ProtocolExhaustedError("Fig.2f protocol exhausted; initialize to replay again.")
        step = self._steps[self._position]
        self._position += 1
        return step
