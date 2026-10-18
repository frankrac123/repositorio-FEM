"""Display transforms only: never mutate physical results or geometry."""
import math


def section_radius(area,scale=1.5):
    if not math.isfinite(area) or area<=0 or not math.isfinite(scale) or scale<=0:
        raise ValueError('Área y escala visual deben ser positivas y finitas.')
    return math.sqrt(area/math.pi)*scale


def signed_color(value,maximum):
    if not math.isfinite(value) or not math.isfinite(maximum):
        raise ValueError('No se pueden representar resultados no finitos.')
    t=min(1.,abs(value)/maximum) if maximum>0 else 0.
    light=(220,231,242)
    target=(31,111,232) if value>=0 else (219,51,74)
    return '#'+''.join(f'{round(a+(b-a)*t):02x}' for a,b in zip(light,target))
