import math
import pytest
from trusslab.result_styles import section_radius,signed_color


def test_display_radius_preserves_area_proportions():
    assert section_radius(4)/section_radius(1)==pytest.approx(2)
    assert section_radius(3,2)==pytest.approx(math.sqrt(3/math.pi)*2)
    with pytest.raises(ValueError):section_radius(-1)


def test_signed_stress_colormap_is_consistent_and_monotone():
    def rgb(color):return tuple(int(color[i:i+2],16) for i in (1,3,5))
    blue=rgb(signed_color(25,25));red=rgb(signed_color(-25,25));light=rgb(signed_color(5,25))
    assert blue[2]>blue[0] and red[0]>red[2]
    assert light[0]>blue[0]
    assert signed_color(0,0)=='#dce7f2'
