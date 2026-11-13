"""Mouth-local targets: speech never moves the chin or jaw contour."""
import numpy as np

UPPER_INNER = [78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308]
LOWER_INNER = [78, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308]
UPPER_OUTER = [61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291]
LOWER_OUTER = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291]


def speech_targets(face):
    mouth = (face[13] + face[14]) / 2
    x = face[:, 0] - mouth[0]
    left, right = sorted([face[78, 0], face[308, 0]])
    f = np.clip((face[:, 0] - left) / max(right-left, .001), 0, 1)
    curve = np.sin(np.pi*f)
    aa = np.zeros_like(face); ih = aa.copy(); ou = aa.copy()
    # Curved lip rims open around fixed corners; no lower-face translation.
    for indices, opening in [(UPPER_INNER, .0008), (LOWER_INNER, -.006),
                             (UPPER_OUTER, .0004), (LOWER_OUTER, -.003)]:
        opening *= 1.5
        aa[indices, 1] = opening * curve[indices]
        ih[indices, 1] = opening * .4 * curve[indices]
        ou[indices, 1] = opening * .65 * curve[indices]
        ih[indices, 0] = x[indices] * .06 * curve[indices]
        ou[indices, 0] = -x[indices] * .17 * curve[indices]
        ou[indices, 2] = .001 * curve[indices]
    # Keep all four lip corners completely fixed at the surrounding face.
    for target in [aa, ih, ou]: target[[61,78,291,308]] = 0
    happy = np.zeros_like(face)
    happy[:, 1] = .0012 * np.exp(-((np.abs(x)-.022)/.012)**2 - ((face[:, 1]-mouth[1])/.015)**2)
    return aa, ih, ou, happy
