import pypattern as pyp


class BaseBottoms(pyp.Component):
    """A base class for all the bottom components.
        Defines common elements: 
        * List of interfaces
        * Presence of the rise value
    """
    def __init__(self, body, design, tag='') -> None:
        """Base bottoms initialization
        """
        super().__init__(
            self.__class__.__name__ if not tag else f'{self.__class__.__name__}_{tag}')
        
        self.body = body
        self.design = design
        
        # Set of interfaces that need to be implemented
        self.interfaces = {
            'top': object()
        }
        
    def get_rise(self):
        """Return a rise value for a given component"""
        return 1.
    
    def eval_rise(self, rise):
        """Evaluate updated hip and waist-related measurements, 
            corresponding to the provided rise value 
        """
        waist, hips = self.body['waist'], self.body['hips']
        hips_level = self.body['hips_line']
        self.adj_hips_depth = rise * hips_level
        self.adj_waist = pyp.utils.lin_interpolation(hips, waist, rise)

        self_adj_back_waist = pyp.utils.lin_interpolation(
            self.body['hip_back_width'], self.body['waist_back_width'], rise)

        return self.adj_waist, self.adj_hips_depth, self_adj_back_waist

class StackableSkirtComponent(BaseBottoms):
    """
        Abstract definition of a skirt that can be stacked with other stackable skirts
        (connecting bottom to another StackableSkirtComponent())
    """

    def __init__(self, body, design, tag='', length=None, rise=None, slit=True, top_ruffles=True) -> None:
        """Skirt initialization

            Extra parameters (length, sleets, top_ruffles) 
            can be used to overwrite parameters in design dictionary
        """
        super().__init__(body, design, tag)
        
        pass

        # Set of interfaces that need to be implemented
        self.interfaces = {
            'top': object(),
            'bottom_f': object(),
            'bottom_b': object(),
            'bottom': object()
        }


