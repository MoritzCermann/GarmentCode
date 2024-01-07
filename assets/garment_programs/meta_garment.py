from assets.garment_programs.tee import *
from assets.garment_programs.godet import *
from assets.garment_programs.bodice import *
from assets.garment_programs.pants import *
from assets.garment_programs.bands import *
from assets.garment_programs.skirt_paneled import *
from assets.garment_programs.skirt_levels import *
from assets.garment_programs.circle_skirt import *
from assets.garment_programs.sleeves import *


class MetaGarment(pyp.Component):
    """Meta garment component
        Depending on parameter values it can generate sewing patterns
    for various dresses and jumpsuit styles and fit them to the body
    measurements
    """
    def __init__(self, name, body, design) -> None:
        super().__init__(name)

        # Upper garment
        upper_name = design['meta']['upper']['v']
        if upper_name: 
            upper = globals()[upper_name]
            self.subs = [upper(body, design)]

        # Define Lower garment
        lower_name = design['meta']['bottom']['v']
        if lower_name:
            Lower_class = globals()[lower_name]
            Lower = Lower_class(body, design)
        else: 
            Lower = None

        # Belt (or not)
        belt_name = design['meta']['wb']['v']
        if belt_name:
            Belt_class = globals()[belt_name]
            
            # Adjust rise to match the Lower garment if needed
            Belt = Belt_class(body, design, Lower.get_rise() if Lower else 1.)

            self.subs.append(Belt)

            # Place below the upper garment 
            if len(self.subs) > 1:
                self.subs[-1].place_by_interface(
                    self.subs[-1].interfaces['top'],
                    self.subs[-2].interfaces['bottom'], 
                    gap=5
                )

                self.stitching_rules.append(
                    (self.subs[-2].interfaces['bottom'],
                     self.subs[-1].interfaces['top']))

        # Attach Lower garment if present
        if lower_name:
            self.subs.append(Lower)
            # Place below the upper garment or self.wb
            if len(self.subs) > 1:
                self.subs[-1].place_by_interface(
                    self.subs[-1].interfaces['top'],
                    self.subs[-2].interfaces['bottom'], 
                    gap=5
                )
                self.stitching_rules.append(
                    (self.subs[-2].interfaces['bottom'],
                     self.subs[-1].interfaces['top']))
