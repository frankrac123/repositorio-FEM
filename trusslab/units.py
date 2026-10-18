"""Canonical units: in, in², kip, ksi, lb and weight density lb/in³.
No implicit mass conversion; dynamics and mass density are outside this solver.
"""
import math
LB_PER_KIP=1000.
def lb_to_kip(value):
    if not math.isfinite(value):raise ValueError('Fuerza no finita.')
    return value/LB_PER_KIP
def kip_to_lb(value):
    if not math.isfinite(value):raise ValueError('Fuerza no finita.')
    return value*LB_PER_KIP
