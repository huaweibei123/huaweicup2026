"""Numerical comparison only; NOT a plan/capacity/execution validator.

Statistics must come from the frozen P2 physical-token rules:
  n, k: eligible op count and core count;
  q: number of BASIC DDR COPYs; W: their integer service sum;
  g: sum_t max(uses_of_local_token_t - 1, 0), an upper bound on spills;
  x: number of cross_links;
  d: maximum service of any basic/spill COPY (use 1 when absent);
  c: maximum individual eligible duration;
  C: tuple/list of eligible-duration sums per core;
  max_bytes: maximum relevant physical-token/COPY size.

Machine premise: each primitive uses binary64, with absolute rounding error
at most one ulp, no unmodelled arithmetic mode/implementation changes.
A's structural certificate and successful E0 returns are separate obligations.
"""
from fractions import Fraction
import sys


def ceilq(x):
    return -(-x.numerator // x.denominator)


def margins(s, *, zero_spill):
    for name in ('n', 'k', 'q', 'g', 'x', 'd', 'c', 'W', 'max_bytes'):
        if type(s[name]) is not int or s[name] < 0:
            raise ValueError('invalid integer statistic: ' + name)
    k, n, q0 = s['k'], s['n'], s['q']
    if not 1 <= k <= 5 or s['d'] < 1 or s['max_bytes'] > 2**31:
        raise ValueError('outside k/size/duration guard')
    if len(s['C']) != k or any(type(v) is not int or v < 0 for v in s['C']):
        raise ValueError('invalid eligible core loads')
    if (sum(s['C']) < n or not q0 <= s['W'] <= q0*s['d']
            or q0 < 2*s['x'] or (n and s['c'] < 1)
            or s['d'] < max(1, (s['max_bytes']+59)//60)):
        raise ValueError('inconsistent counts/work')
    if zero_spill and s['x']:
        raise ValueError('A requires no cross_links')
    q = q0 if zero_spill else q0 + 2*s['g']
    r = n + q + s['x'] + 1
    if r > 1_000_000:
        raise ValueError('outside global-event guard')
    if zero_spill and n + q + 1 > 100_000:
        raise ValueError('outside conservative local-iteration guard')
    if q == 0:
        return (0 if zero_spill else None), 0
    h = 2*k
    jump = max(s['c'], h*s['d'], 500 if s['x'] else 0) + 2
    horizon = (r + h + 2)*jump
    p = max(1, (horizon - 1).bit_length() + 1)
    if p > 36:
        raise ValueError('outside floating-point magnitude guard')
    beta = 32*(h + 1)**2*(Fraction(1, 2**(52-p)) + Fraction(1, 2**29))
    upper_error = 2*q + ceilq((r + 3*q)*beta) if zero_spill else None
    lower_error = ceilq((2*r + (h + 2)*q)*beta)
    return upper_error, lower_error


def gate(a, b, *, a_structure_certified, ieee_ops_attested):
    """Return a CONDITIONAL comparison; do not infer execution success."""
    f = sys.float_info
    if not ieee_ops_attested or (f.radix, f.mant_dig, f.max_exp) != (2, 53, 1024):
        raise ValueError('binary64 machine premise not established')
    if not a_structure_certified:
        raise ValueError('A structural/capacity certificate is missing')
    if a['n'] != b['n'] or a['k'] != b['k'] or sum(a['C']) != sum(b['C']):
        raise ValueError('A/B do not describe the same eligible workload')
    ea, _ = margins(a, zero_spill=True)
    _, eb = margins(b, zero_spill=False)
    u, lower = max(a['C'], default=0) + a['W'], b['W']
    return {'conditional_prefer_A': u + ea < lower - eb,
            'U_A': u, 'L_B': lower, 'epsilon_A': ea, 'epsilon_B': eb,
            'requires_successful_E0_returns': True}
