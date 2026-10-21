"""Ozone transport in the liquid film on a spinning substrate with centre dispense.

Hydrodynamics: the steady film on a rotating disc where centrifugal force balances viscous
shear (inertia, Coriolis force and waves neglected), the 'Nusselt' film of Emslie, Bonner and
Peck (1958) J. Appl. Phys. 29, 858, with a feed Q:

    h(r) = (3 nu Q / (2 pi w^2 r^2))^(1/3)          u(r, z) = (w^2 r / nu) (h z - z^2 / 2)

The thickness equals the correlation h = 0.782 (nu Q)^(1/3) w^(-2/3) r^(-2/3) of Lepehin and
Riabchuk (1975), as listed by Bhatelia et al. (2009), 7th Int. Conf. CFD in the Minerals and
Process Industries. Measured films are thicker near the centre, where inertia matters, and can
be up to about 40 % thicker because of waves (Espig and Hoyle 1965, cited by Bhatelia et al.).

Mass transfer: because the velocity profile is self-similar, the streamlines lie at fixed
fractions zeta = z/h of the film thickness. The film is divided into stream tubes; in each,
ozone is carried outward, diffuses to the neighbouring tubes, and decomposes. At the wall it
is consumed by the resist (diffusion-limited by default, or a first-order surface reaction);
at the free surface it is in equilibrium with the gas above the film (liquid-side control, as
for any sparingly soluble gas). The equations are marched outward in r with an implicit Euler
step and Newton iterations; the ozone balance closes to rounding error.
"""
import math
from dataclasses import dataclass, field

import numpy as np


@dataclass
class FilmInput:
    Q: float                 # liquid flow, m3/s
    omega: float             # angular speed, rad/s
    R: float                 # substrate radius, m
    c_in: float              # dissolved ozone at the nozzle, mol/m3
    nu: float                # kinematic viscosity, m2/s
    D: float                 # ozone diffusivity, m2/s (already multiplied by any enhancement)
    k1: float                # first-order decomposition, 1/s
    k2: float                # second-order decomposition, m3/(mol s)
    c_surface: float = 0.0   # dissolved ozone in equilibrium with the gas above the film, mol/m3;
                             # None closes the free surface (used for checks)
    k_wall: float = math.inf  # surface reaction rate constant at the resist, m/s (inf: diffusion-limited,
                             # 0: inert wall)
    r0: float = 5e-3         # radius where the film model starts (edge of the impingement zone), m
    n_layers: int = 48
    n_steps: int = 400
    r_inject: float = None   # optional second dispense: radius where a ring of nozzles adds liquid, m
    Q_inject: float = 0.0    # flow added there, m3/s
    c_inject: float = 0.0    # dissolved ozone in the added liquid, mol/m3


@dataclass
class FilmResult:
    r: np.ndarray            # radii of the stations, m (first is r0)
    h: np.ndarray            # film thickness, m
    wall_flux: np.ndarray    # ozone flux into the resist, mol/(m2 s)
    surface_flux: np.ndarray  # ozone flux from the gas into the film, mol/(m2 s) (negative: loss)
    c_wall_layer: np.ndarray  # ozone in the layer next to the wall, mol/m3
    c_mean: np.ndarray       # flow-weighted mean ozone, mol/m3
    zeta: np.ndarray         # layer centres as fractions of the thickness
    profiles: dict = field(default_factory=dict)   # radius -> concentration across the film
    budget: dict = field(default_factory=dict)     # ozone fates over the whole substrate, mol/s
    inertia: np.ndarray = None                     # inertia / viscous force ratio along r


def film_thickness(r, Q, omega, nu):
    return (3.0 * nu * Q / (2.0 * math.pi * omega ** 2 * r ** 2)) ** (1.0 / 3.0)


def inertia_ratio(r, Q, omega, nu):
    """Rough ratio of radial inertia to viscous force, (u h^2)/(nu r) with u the mean velocity."""
    h = film_thickness(r, Q, omega, nu)
    return Q * h / (2.0 * math.pi * nu * r ** 2)


def _layers(n):
    """Layer faces clustered towards the wall and the free surface."""
    s = np.linspace(0.0, 1.0, n + 1)
    faces = 0.5 * (1.0 - np.cos(np.pi * s))
    centres = 0.5 * (faces[:-1] + faces[1:])
    return faces, centres


def _stations(r0, R, n):
    """Radial stations, fine near r0 where the concentration boundary layers start."""
    s = np.linspace(0.0, 1.0, n + 1)
    return r0 + (R - r0) * s ** 2


def _thomas(a, b, c, d):
    n = len(b)
    cp, dp = np.empty(n), np.empty(n)
    cp[0], dp[0] = c[0] / b[0], d[0] / b[0]
    for i in range(1, n):
        m = b[i] - a[i] * cp[i - 1]
        cp[i] = c[i] / m if i < n - 1 else 0.0
        dp[i] = (d[i] - a[i] * dp[i - 1]) / m
    x = np.empty(n)
    x[-1] = dp[-1]
    for i in range(n - 2, -1, -1):
        x[i] = dp[i] - cp[i] * x[i + 1]
    return x


def _inject(c, frac_faces, Q_old, Q_new, c_add):
    """Concentrations in the tubes after liquid is added on top of the film. The old liquid keeps
    its order and fills the part of the new film next to the wall, the added liquid lies on top;
    each tube gets the flow-weighted mean of what falls into it, so the ozone flux is conserved.
    frac_faces: cumulative fraction of the flow at the tube faces (0 at the wall, 1 at the surface)."""
    split = Q_old / Q_new
    old_faces = frac_faces * split                 # where the old tubes end up, as fractions of the new flow
    out = np.empty_like(c)
    for j in range(len(c)):
        a, b = frac_faces[j], frac_faces[j + 1]
        total = 0.0
        for i in range(len(c)):
            lo, hi = max(a, old_faces[i]), min(b, old_faces[i + 1])
            if hi > lo:
                total += (hi - lo) * c[i]
        if b > split:
            total += (b - max(a, split)) * c_add
        out[j] = total / (b - a)
    return out


def solve(inp: FilmInput, profile_radii=()):
    faces, zc = _layers(inp.n_layers)
    dz = np.diff(faces)
    F = faces ** 2 / 2.0 - faces ** 3 / 6.0
    frac = 3.0 * F                                           # cumulative fraction of the flow at the faces
    Q = inp.Q
    q = 3.0 * Q / (2.0 * math.pi) * np.diff(F)               # flow per radian in each tube, m3/s
    injected = inp.r_inject is None or inp.Q_inject <= 0.0
    dzc = np.diff(zc)                                        # distances between layer centres
    rs = _stations(inp.r0, inp.R, inp.n_steps)
    c = np.full(inp.n_layers, inp.c_in)
    N = inp.n_layers
    out_wall, out_surf, out_cw, out_cm, hs = [], [], [], [], []
    tot_wall = tot_surf = tot_dec = 0.0
    profiles = {}
    want = sorted(profile_radii)

    closed = inp.c_surface is None
    cs = 0.0 if closed else inp.c_surface

    def fluxes(cv, r, h):
        if inp.k_wall == 0:
            gw = 0.0
        elif math.isinf(inp.k_wall):
            gw = r * inp.D / (h * zc[0])
        else:
            gw = r / (1.0 / inp.k_wall + h * zc[0] / inp.D)
        gs = 0.0 if closed else r * inp.D / (h * (1.0 - zc[-1]))
        return gw, gs

    h0 = film_thickness(rs[0], Q, inp.omega, inp.nu)
    gw0, gs0 = fluxes(c, rs[0], h0)
    out_wall.append(gw0 * c[0] / rs[0])
    out_surf.append(gs0 * (cs - c[-1]) / rs[0])
    out_cw.append(c[0]); out_cm.append(inp.c_in); hs.append(h0)
    for n in range(1, len(rs)):
        r, dr = rs[n], rs[n] - rs[n - 1]
        if not injected and r >= inp.r_inject:
            c = _inject(c, frac, Q, Q + inp.Q_inject, inp.c_inject)
            Q = Q + inp.Q_inject
            q = 3.0 * Q / (2.0 * math.pi) * np.diff(F)
            injected = True
        h = film_thickness(r, Q, inp.omega, inp.nu)
        g = r * inp.D / (h * dzc)                            # conductances between layers, per radian
        gw, gs = fluxes(c, r, h)
        V = r * h * dz                                       # layer volume per radian per unit dr
        old = c.copy()
        x = c.copy()
        for _ in range(8):
            rate = inp.k1 * x + inp.k2 * x * x
            drate = inp.k1 + 2.0 * inp.k2 * x
            lower, diag, upper = np.zeros(N), q / dr + V * drate, np.zeros(N)
            res = q / dr * (x - old) + V * rate
            diag[:-1] += g
            diag[1:] += g
            upper[:-1] = -g
            lower[1:] = -g
            res[:-1] -= g * (x[1:] - x[:-1])
            res[1:] -= g * (x[:-1] - x[1:])
            diag[0] += gw
            res[0] += gw * x[0]
            diag[-1] += gs
            res[-1] -= gs * (cs - x[-1])
            step = _thomas(lower, diag, upper, -res)
            x = x + step
            if np.max(np.abs(step)) <= 1e-12 * max(inp.c_in, 1e-30):
                break
        c = x
        wall = gw * c[0]                                     # per radian, mol/(s m) of radius
        surf = gs * (cs - c[-1])
        dec = float(np.sum(V * (inp.k1 * c + inp.k2 * c * c)))
        tot_wall += 2.0 * math.pi * wall * dr
        tot_surf += 2.0 * math.pi * surf * dr
        tot_dec += 2.0 * math.pi * dec * dr
        out_wall.append(wall / r)
        out_surf.append(surf / r)
        out_cw.append(c[0])
        out_cm.append(float(np.sum(q * c) / np.sum(q)))
        hs.append(h)
        while want and r >= want[0] - 1e-12:
            profiles[want.pop(0)] = c.copy()
    out_edge = 2.0 * math.pi * float(np.sum(q * c))
    r_arr = np.asarray(rs)
    wall_flux = np.asarray(out_wall)
    # Under the nozzle (r < r0) the jet impinges; that zone is not modelled and is left out of
    # the ozone budget (it is 0.1 % of a 300 mm wafer for r0 = 5 mm).
    fed = inp.Q * inp.c_in + (inp.Q_inject * inp.c_inject if inp.r_inject is not None else 0.0)
    budget = {
        'in': fed,
        'resist': tot_wall,
        'gas_exchange': tot_surf,
        'decomposed': tot_dec,
        'edge': out_edge,
        'closure': (fed + tot_surf) - (tot_wall + tot_dec + out_edge),
    }
    return FilmResult(r=r_arr, h=np.asarray(hs), wall_flux=wall_flux, surface_flux=np.asarray(out_surf),
                      c_wall_layer=np.asarray(out_cw), c_mean=np.asarray(out_cm), zeta=zc,
                      profiles=profiles, budget=budget,
                      inertia=np.array([inertia_ratio(r, inp.Q if inp.r_inject is None or r < inp.r_inject
                                                      else inp.Q + inp.Q_inject, inp.omega, inp.nu) for r in r_arr]))


def area_average(r, y, r_min):
    """Area-weighted mean of y(r) over the disc. Inside r_min (the impingement zone and the start
    of the boundary layers, where the film model is singular) y is taken equal to y(r_min)."""
    r, y = np.asarray(r), np.asarray(y)
    ym = float(np.interp(r_min, r, y))
    keep = r > r_min
    rr = np.concatenate(([r_min], r[keep]))
    yy = np.concatenate(([ym], y[keep]))
    outer = np.trapezoid(2.0 * math.pi * rr * yy, rr)
    return (math.pi * r_min ** 2 * ym + outer) / (math.pi * r[-1] ** 2)
