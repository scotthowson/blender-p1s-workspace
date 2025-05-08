"""
A collection of 2D numpy shape generators
"""

from argparse import ArgumentError
from dataclasses import dataclass
from functools import cached_property
from typing import NamedTuple
import numpy as np


class Shape2D(NamedTuple):
    verts: np.ndarray
    faces: np.ndarray


@dataclass
class _Cross():
    x_len: float = 0
    x_width: float = 0
    y_len: float = 0
    y_height: float = 0

    @cached_property
    def _is_x_rect(self):
        def _attrib_tests(self):
            yield self.y_len < self.x_len
            yield self.x_width != 0
        return all(_attrib_tests)

    @cached_property
    def _is_y_rect(self):
        def _attrib_test(self):
            yield self.x_len < self.y_len
            yield self.y_width != 0
        return all(_attrib_test())

    def _create_rectangle(self):
        if self._is_x_rect:
            half_width = self.x_width / 2
            half_length = self.x_len / 2

            verts = np.array((
                (-half_length, half_width),
                (half_length, half_width),
                (half_length, -half_width),
                (-half_length, -half_width),
            ))
        else:
            half_width = self.y_width / 2
            half_length = self.y_len / 2

            verts = np.array((
                (-half_width, half_length),
                (half_width, half_length),
                (half_width, -half_length),
                (-half_width, -half_length),
            ))

        faces = np.array([[0, 1, 2, 3]])
        return Shape2D(verts, faces)

    def _create_cross(self):
        pass

    def create(self):
        if any((self._is_x_rect, self._is_y_rect)):
            return self._create_rectangle()
        return self._create_cross()


def cross(
    x_len: float = 0,
    x_width: float = 0,
    y_len: float = 0,
    y_height: float = 0,
) -> Shape2D:
    pass


def polygon(sides: int = 3) -> Shape2D:
    if sides < 3:
        raise ArgumentError("Sides arg < 3")

    angles = np.linspace(start=0.0, stop=(2 * np.pi), num=sides, endpoint=False)
    coords_gen = [(np.sin(angle), np.cos(angle)) for angle in angles]
    faces = np.array([list(range(sides))])
    return Shape2D(np.asarray(coords_gen), faces)


if __name__ == "__main__":
    print(polygon(3))
