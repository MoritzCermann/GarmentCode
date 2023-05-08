
from copy import copy
import numpy as np
from numpy.linalg import norm
import svgpathtools as svgpath
from scipy.optimize import minimize

# Custom
from .edge import EdgeSequence, Edge, CurveEdge
from .generic_utils import vector_angle, close_enough, c_to_list, list_to_c
from .interface import Interface
from . import flags

class EdgeSeqFactory:
    """Create EdgeSequence objects for some common edge seqeunce patterns
    """

    @staticmethod
    def from_verts(*verts, loop=False):
        """Generate edge sequence from given vertices. If loop==True, the method also closes the edge sequence as a loop
        """
        # TODO Curvatures -- on the go

        seq = EdgeSequence(Edge(verts[0], verts[1]))
        for i in range(2, len(verts)):
            seq.append(Edge(seq[-1].end, verts[i]))

        if loop:
            seq.append(Edge(seq[-1].end, seq[0].start))
        
        seq.isChained()
        return seq

    @staticmethod
    def from_fractions(start, end, frac=[1]):
        """A sequence of edges between start and end wich lengths are distributed
            as specified in frac list 
        Parameters:
            * frac -- list of legth fractions. Every entry is in (0, 1], 
                all entries sums up to 1
        """
        # TODO Deprecated? 
        # FIXME From fractions should be straight in the names??
        frac = [abs(f) for f in frac]
        if not close_enough(fsum:=sum(frac), 1, 1e-4):
            raise RuntimeError(f'EdgeSequence::Error::fraction is incorrect. The sum {fsum} is not 1')

        vec = np.asarray(end) - np.asarray(start)
        verts = [start]
        for i in range(len(frac) - 1):
            verts.append(
                [verts[-1][0] + frac[i]*vec[0],
                verts[-1][1] + frac[i]*vec[1]]
            )
        verts.append(end)
        
        return EdgeSeqFactory.from_verts(*verts)

    @staticmethod
    def side_with_cut(start=(0,0), end=(1,0), start_cut=0, end_cut=0):
        """ Edge with internal vertices that allows to stitch only part of the border represented
            by the long side edge

            start_cut and end_cut specify the fraction of the edge to to add extra vertices at
        """
        # TODO Curvature support? -- if needed in modeling

        nstart, nend = np.array(start), np.array(end)
        verts = [start]

        if start_cut > 0:
            verts.append((start + start_cut * (nend-nstart)).tolist())
        if end_cut > 0:
            verts.append((end - end_cut * (nend-nstart)).tolist())
        verts.append(end)

        edges = EdgeSeqFactory.from_verts(*verts)

        return edges

    #DRAFT
    @staticmethod
    def side_with_dart_by_width(start=(0,0), end=(100,0), width=5, depth=10, dart_position=50, opening_angle=180, right=True, modify='both', panel=None):
        """Create a seqence of edges that represent a side with a dart with given parameters
        Parameters:
            * start and end -- vertices between which side with a dart is located
            * width -- width of a dart opening
            * depth -- depth of a dart (distance between the opening and the farthest vertex)
            * dart_position -- position along the edge (from the start vertex)
            * opening angle (deg) -- angle between side edges after the dart is stitched (as evaluated opposite from the dart). default = 180 (straight line)
            * right -- whether the dart is created on the right from the edge direction (otherwise created on the left). Default - Right (True)
            * modify -- which vertex position to update to accomodate for contraints: 'start', 'end', or 'both'. Default: 'both'

        Returns: 
            * Full edge with a dart
            * References to dart edges
            * References to non-dart edges
            * Suggested dart stitch

        NOTE: (!!) the end of the edge might shift to accomodate the constraints
        NOTE: The routine makes sure that the the edge is straight after the dart is stitched
        NOTE: Darts always have the same length on the sides
        """
        # TODO Curvatures?? -- on edges, dart sides
        # TODO Multiple darts on one side (can we make this fucntions re-usable/chainable?)
        # TODO Angled darts (no 90 degree angles on connection)
        # TODO width from fixed L and target length

        # Targets
        v0, v1 = np.asarray(start), np.asarray(end)
        L = norm(v1 - v0)
        d0, d1 = dart_position, L - dart_position
        depth_perp = np.sqrt((depth**2 - (width / 2)**2))
        dart_side = depth

        if d1 < 0:
            raise ValueError(f'EdgeFactory::Error::Invalid value supplied for dart position: {d0} out of {L}')

        # Extended triangle -- sides
        delta_l = dart_side * width / (2 * depth_perp)  # extention of edge length beyong the dart points
        side0, side1 = d0 + delta_l, d1 + delta_l
        
        # long side (connects original vertices)
        alpha = abs(np.arctan(width / 2 / depth_perp))  # half of dart tip angle
        top_angle = np.pi - 2*alpha  # top of the triangle (v0, imaginative dart top, v1)
        long_side = np.sqrt(side0**2 + side1**2 - 2*side0*side1*np.cos(top_angle))
        
        # angles of extended triangle
        sin0, sin1 = side1 * np.sin(top_angle) / long_side, side0 * np.sin(top_angle) / long_side
        angle0, angle1 = np.arcsin(sin0), np.arcsin(sin1)

        # Find the location of dart points: start of dart cut
        p1x = d0 * np.cos(angle0)
        p1y = d0 * sin0
        p1 = np.array([p1x, p1y])

        p1 = _rel_to_abs_coords(v0, v1, p1)

        # end of dart cut
        p2x = long_side - (d1 * np.cos(angle1))
        p2y = d1 * sin1
        p2 = np.array([p2x, p2y])
        p2 = _rel_to_abs_coords(v0, v1, p2)

        # Tip of the dart
        p_vec = p2 - p1
        p_perp = np.array([-p_vec[1], p_vec[0]])
        p_perp = p_perp / norm(p_perp) * depth_perp

        p_tip = p1 + p_vec / 2 - p_perp

        # New location of the dart end to satisfy the requested length
        new_end = _rel_to_abs_coords(v0, v1, np.array([long_side, 0]))
        shift = new_end - v1
        end[:] = _rel_to_abs_coords(v0, v1, np.array([long_side, 0]))

        # Gather all together
        dart_shape = EdgeSeqFactory.from_verts(p1.tolist(), p_tip.tolist(), p2.tolist())
        if not right:
            # flip dart to be the left of the vector
            dart_shape.reflect(start, end)

        dart_shape.insert(0, Edge(start, dart_shape[0].start))
        dart_shape.append(Edge(dart_shape[-1].end, end))

        # re-distribute the changes & adjust the opening angle as requested
        angle_diff = np.deg2rad(180 - opening_angle) * 1 if right else -1    # TODO right/left dart modificaiton flip not tested
        if modify == 'both':
            dart_shape.translate_by(-shift / 2)
            dart_shape[0].reverse().rotate(-angle_diff / 2).reverse()
            dart_shape[-1].rotate(angle_diff / 2)
        elif modify == 'end':
            # Align the beginning of the dart with original direction
            dart_shape.rotate(vector_angle(p1-v0, v1-v0))
            dart_shape[-1].rotate(angle_diff)
        elif modify == 'start':
            # Align the end of the dart with original direction & shift the change onto the start vertex
            dart_shape.translate_by(-shift)
            dart_shape.reverse()  # making the end vertex the start (to rotate around)
            dart_shape.rotate(vector_angle(p2-new_end, -(v1-v0)))
            dart_shape[-1].rotate(-angle_diff)
            dart_shape.reverse()  # original order

        # prepare the interfaces to conveniently create stitches for a dart and non-dart edges
        dart_stitch = None if panel is None else (Interface(panel, dart_shape[1]), Interface(panel, dart_shape[2]))
        
        out_interface = EdgeSequence(dart_shape[0], dart_shape[-1]) 
        out_interface = out_interface if panel is None else Interface(panel, out_interface)

        return dart_shape, dart_shape[1:-1], out_interface, dart_stitch

    @staticmethod
    def side_with_dart_by_len(start=(0,0), end=(50,0), target_len=35, depth=10, dart_position=25, dart_angle=90, right=True, panel=None, tol=1e-4):
        """Create a seqence of edges that represent a side with a dart with given parameters
        Parameters:
            * start and end -- vertices between which side with a dart is located
            * target_len 
            * depth -- depth of a dart (distance between the opening and the farthest vertex)
            * dart_position -- position along the edge (from the start vertex)
            * right -- whether the dart is created on the right from the edge direction (otherwise created on the left). Default - Right (True)

        Returns: 
            * Full edge with a dart
            * References to dart edges
            * References to non-dart edges
            * Suggested dart stitch

        NOTE: (!!) the end of the edge might shift to accomodate the constraints
        NOTE: The routine makes sure that the the edge is straight after the dart is stitched
        NOTE: Darts always have the same length on the sides
        """
        # TODO Curvatures?? -- on edges, dart sides
        # TODO Multiple darts on one side (can we make this fucntions re-usable/chainable?)
        # TODO Angled darts (no 90 degree angles on connection)
        # TODO Opening angle control?

        # Targets
        v0, v1 = np.asarray(start), np.asarray(end)
        L = norm(v0 - v1)
        d0, d1 = dart_position, target_len - dart_position

        if (d0 + d1) >= L:
            raise ValueError(f'EdgeFactory::Error::Invalid value supplied for dart position: {d0} does not satisfy triangle inequality for edge length {norm(v0 - v1)}')

        # Initial guess
        v = (v1 - v0) / L
        p0 = v0 + v * L * (d0 / (d0 + d1))
        p1 = copy(p0)
        vperp = np.asarray([v[1], -v[0]])
        p_tip = p0 + depth * vperp
        guess = np.concatenate([p0, p_tip, p1])

        # Solve for dart constraints
        out = minimize(_fit_dart, guess, args=(v0, v1, d0, d1, depth, dart_angle))
        if not close_enough(out.fun, tol=tol):
            print(out)
            raise ValueError(f'EdgeFactory::Error::Solving dart was unsuccessful for L: {L}, Ds: {d0, d1}, Depth: {depth}')

        p0, p_tip, p1 = out.x[:2], out.x[2:4], out.x[4:]

        # As edge seq object
        dart_shape = EdgeSeqFactory.from_verts(p0.tolist(), p_tip.tolist(), p1.tolist())

        # Check direction
        right_position = np.sign(np.cross(v1 - v0, p_tip - v0)) == -1 
        if not right and right_position or right and not right_position:
            # flip dart to match the requested direction
            dart_shape.reflect(start, end)

        dart_shape.insert(0, Edge(start, dart_shape[0].start))
        dart_shape.append(Edge(dart_shape[-1].end, end))

        # prepare the interfaces to conveniently create stitches for a dart and non-dart edges
        dart_stitch = None if panel is None else (Interface(panel, dart_shape[1]), Interface(panel, dart_shape[2]))
        
        out_interface = EdgeSequence(dart_shape[0], dart_shape[-1]) 
        out_interface = out_interface if panel is None else Interface(panel, out_interface)

        return dart_shape, dart_shape[1:-1], out_interface, dart_stitch

    @staticmethod
    def dart_shape(width, depth):
        """Shape of simple triangular dart"""
        depth_perp = np.sqrt((depth**2 - (width / 2)**2))

        return EdgeSeqFactory.from_verts([0, 0], [width / 2, -depth_perp], [width, 0])

    @staticmethod
    def curve_from_extreme(start, end, target_extreme):
        """Create (Quadratic) curve edge that 
            has an extreme point as close as possible to target_extreme
            with extreme point aligned with it
        """
        rel_target = _abs_to_rel_2d(start, end, target_extreme)

        out = minimize(
            _fit_y_extremum, 
            rel_target[1],    
            args=(rel_target)
        )

        if not out.success:
            print('Curve From Extreme::Warning::Optimization not successful')
            if flags.VERBOSE:
                print(out)

        cp = [rel_target[0], out.x.item()]

        return CurveEdge(start, end, control_points=[cp], relative=True)

# Utils
# TODOLOW Move to generic_utils
def _rel_to_abs_coords(start, end, vrel):
    """Convert coordinates specified relative to vector v2 - v1 to world coords"""
    # TODOLOW It's in the edges?
    start, end, vrel = np.asarray(start), np.asarray(end), np.asarray(vrel)
    vec = end - start
    vec = vec / norm(vec)
    vec_perp = np.array([-vec[1], vec[0]])
    
    new_start = start + vrel[0] * vec
    new_point = new_start + vrel[1] * vec_perp

    return new_point 

def _abs_to_rel_2d(start, end, point):
    """Convert control points coordinates from absolute to relative"""
    # TODOLOW It's in the edge class?
    start, end = np.asarray(start), np.asarray(end)
    edge = end - start
    edge_len = norm(edge)

    point_vec = np.asarray(point) - start

    converted = [None, None]
    # X
    # project control_vec on edge by dot product properties
    projected_len = edge.dot(point_vec) / edge_len 
    converted[0] = projected_len / edge_len
    # Y
    control_projected = edge * converted[0]
    vert_comp = point_vec - control_projected  
    converted[1] = norm(vert_comp) / edge_len

    # Distinguish left&right curvature
    converted[1] *= -np.sign(np.cross(point_vec, edge)) 
    
    return np.asarray(converted)

def _fit_dart(coords, v0, v1, d0, d1, depth, theta=90):
    """Placements of three dart points respecting the constraints"""
    p0, p_tip, p1 = coords[:2], coords[2:4], coords[4:]
    error = {}

    # Distance constraints
    error['d0'] = (norm(p0 - v0) - d0)**2
    error['d1'] = (norm(p1 - v1) - d1)**2

    # Depth constraint
    error['depth0'] = (norm(p0 - p_tip) - depth)**2
    error['depth1'] = (norm(p1 - p_tip) - depth)**2

    # Angle constraint 
    # allows for arbitraty angle of the dart tip w.r.t. edge side after stitching
    theta = np.deg2rad(theta)
    error['angle0'] = (np.dot(p_tip - p0, v0 - p0) - np.cos(theta) * d0 * depth)**2
    # cos(pi - theta) = - cos(theta)
    error['angle1'] = (np.dot(p_tip - p1, v1 - p1) + np.cos(theta) * d1 * depth)**2

    # Maintain P0, P1 on the same side w.r.t to v0-v1
    error['side'] = (_softsign(np.cross(v1 - v0, p1 - v0)) - _softsign(np.cross(v1 - v0, p0 - v0)))**2 / 4

    return sum(error.values())

def _softsign(x):
    return x / (abs(x) + 1)

def _extreme_points(curve, on_x=False, on_y=True):
    """Return extreme points of the current edge
        NOTE: this does NOT include the border vertices of an edge
    """
    # TODOLOW it repeats code from Edge() class in a way
    # Variation of https://github.com/mathandy/svgpathtools/blob/5c73056420386753890712170da602493aad1860/svgpathtools/bezier.py#L197
    poly = svgpath.bezier2polynomial(curve, return_poly1d=True)
    
    x_extremizers, y_extremizers = [], []
    if on_y:
        y = svgpath.imag(poly)
        dy = y.deriv()
        
        y_extremizers = svgpath.polyroots(dy, realroots=True,
                                            condition=lambda r: 0 < r < 1)
    if on_x:
        x = svgpath.real(poly)
        dx = x.deriv()
        x_extremizers = svgpath.polyroots(dx, realroots=True,
                                    condition=lambda r: 0 < r < 1)
    all_extremizers = x_extremizers + y_extremizers

    extreme_points = np.array([c_to_list(curve.point(t)) for t in all_extremizers])

    return extreme_points

def _fit_y_extremum(cp_y, target_location):
    """ Fit the control point of basic [[0, 0] -> [1, 0]] Quadratic Bezier s.t. 
        it's expremum is close to target location.

        * cp_y - initial guess for Quadratic Bezier control point y coordinate
            (relative to the edge)
        * target_location -- target to fit extremum to -- 
            expressed in RELATIVE coordinates to your desired edge
    """

    control_bezier = np.array([
        [0, 0], 
        [target_location[0], cp_y[0]], 
        [1, 0]
    ])
    params = list_to_c(control_bezier)
    curve = svgpath.QuadraticBezier(*params)

    extremum = _extreme_points(curve)

    if not len(extremum):
        raise RuntimeError('No extreme points!!')

    diff = np.linalg.norm(extremum - target_location)

    return diff**2 