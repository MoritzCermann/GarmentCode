

import pypattern as pyp

class BodyParameters(pyp.BodyParametrizationBase):
    """Custom class that defines calculated body parameters
    """
    def __init__(self, param_file='') -> None:
        super().__init__(param_file)

    def eval_dependencies(self, key=None):
        super().eval_dependencies(key)

        if key in ['height', 'head_l', 'waist_line', 'hips_line', None]:
            self.params['_waist_level'] = self.params['height'] - self.params['head_l'] - self.params['waist_line']
            self.params['_leg_length'] = self.params['_waist_level'] - self.params['hips_line']
        if key in ['sholder_w', None]:
            # Correct sleeve line location is a little closer to the neck
            # than the true shoulder width
            self.params['_base_sleeve_balance'] = self.params['sholder_w'] - 4
            self.params['_base_armhole_incline'] = max(1, (self.params['back_width'] - self.params['_base_sleeve_balance']) / 2)

if __name__ == "__main__":

    body_file = './assets/body_measurments/f_smpl_avg.yaml'

    body = BodyParameters(body_file)

    body.save('./Logs')