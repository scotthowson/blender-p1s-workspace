from dataclasses import dataclass, field
from functools import cached_property
from math import radians, sqrt
import numpy as np

from .custom_types import ThreadProfile


@dataclass
class ISO_68_1(ThreadProfile):
    """
    ISO 68-1 Metric Screw Threads
    h = sqrt(3) / 2 * p
    thread_angle = 60 degrees
    """

    pitch: float
    length: float
    major_diameter: float
    starts: int
    internal: bool = False
    minor_diameter: float = field(init=False)
    height: float = field(init=False)
    thread_angle: float = radians(60)
    depth: float = field(init=False)
    pitch_diameter: float = field(init=False)
    root_width: float = field(init=False)
    crest_width: float = field(init=False)
    crest_truncation: float = field(init=False)
    root_truncation: float = field(init=False)
    sharp_crest: bool = False
    # tolerance: float = 0.0

    def __post_init__(self):
        self.height = sqrt(3) / 2 * self.pitch
        self.minor_diameter = self.major_diameter - (2 * (5 / 8 * self.height))
        self.depth = 3 / 8 * self.height
        self.root_width = self.pitch / 4
        self.crest_width = self.pitch / 8
        self.root_truncation = self.height / 4
        self.crest_truncation = self.height - self.root_truncation - self.depth


@dataclass
class Custom(ThreadProfile):
    """
    Custom thread profile:
        - Major Diameter
        - Minor Diameter
        - Pitch
        - Crest Percentage
        - Root Percentage

    """

    pitch: float
    length: float
    minor_diameter: float
    major_diameter: float
    starts: int
    root_width: float  # factor
    crest_width: float  # factor
    internal: bool = False
    height: float = field(init=False)
    thread_angle: float = radians(60)
    depth: float = field(init=False)
    pitch_diameter: float = field(init=False)
    crest_truncation: float = field(init=False)
    root_truncation: float = field(init=False)
    sharp_crest: bool = False
    # tolerance: float = 0.0

    def __post_init__(self):
        # scaler = (self.root_width + self.crest_width) / self.pitch
        self.root_width *= self.pitch
        self.crest_width *= self.pitch

        self.height = sqrt(3) / 2 * self.pitch
        self.depth = self.major_diameter - self.minor_diameter
        self.root_truncation = self.height / 4
        self.crest_truncation = self.height - self.root_truncation - self.depth


PROFILES = {subclass.__name__: subclass for subclass in ThreadProfile.__subclasses__()}
PROFILE_NAMES = [
    subclass.__name__.upper() for subclass in ThreadProfile.__subclasses__()
]
