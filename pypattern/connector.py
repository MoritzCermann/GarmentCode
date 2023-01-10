from numpy.linalg import norm

# Custom
from .edge_factory import EdgeSeqFactory
from .interface import Interface
from ._generic_utils import close_enough

class StitchingRule():
    """High-level stitching instructions connecting two component interfaces"""
    def __init__(self, int1, int2) -> None:
        """Supported combinations: 
            * edges-to-edges (same number of edges on both sides, matching order)
            * T-stitch: multiple edges to single edge
        """
        # TODO Multiple interfaces in the same stitch (3-way stitches?)
        self.int1 = int1
        self.int2 = int2

        if not self.isMatching():
            self.match_edge_count()
            

    def isMatching(self):
        return len(self.int1) == len(self.int2)


    def isTraversalMatching(self):
        """Check if the traversal direction of edge sequences matches or needs to be swapped"""

        if len(self.int1.edges) > 1:
            # Make sure the direction is matching
            # 3D distance between corner vertices
            start_1 = self.int1.panel[0].point_to_3D(self.int1.edges[0].start)
            start_2 = self.int2.panel[0].point_to_3D(self.int2.edges[0].start)

            end_1 = self.int1.panel[-1].point_to_3D(self.int1.edges[-1].end)
            end_2 = self.int2.panel[-1].point_to_3D(self.int2.edges[-1].end)
            
            stitch_dist_straight = norm(start_2 - start_1) + norm(end_2 - end_1)
            stitch_dist_reverse = norm(start_2 - end_1) + norm(end_2 - start_1)

            if stitch_dist_reverse < stitch_dist_straight:
                # We need to swap traversal direction
                return False
        return True


    def match_edge_count(self, tol=0.1):
        """ Subdivide the interface edges on both sides s.t. they have the matching number of edges on each side and
            can be safely connected
        
            Serializable format does not natively support t-stitches, 
            so the longer edges needs to be broken down into matching segments
            # SIM specific
        """

        # Eval the fraction corresponding to every segment in the "from" interface
        # Using projecting edges to match desired gather patterns
        lengths1 = self.int1.projecting_edges().lengths()
        if not self.isTraversalMatching():      # Make sure connectivity order will be correct even if edge directions are not aligned
            lengths1.reverse()

        lengths2 = self.int2.projecting_edges().lengths()
        if not self.isTraversalMatching():      # Make sure connectivity order will be correct even if edge directions are not aligned
            lengths2.reverse()   # match the other edge orientation before passing on

        if not close_enough(sum(lengths1), sum(lengths2), tol):
            # TODO Can we do it for fraction now that we figured out length??
            raise RuntimeError(f'{self.__class__.__name__}::Error::Projected edges do not match for two stitches')

        self._match_side_count(self.int1, lengths2, tol=tol)
        self._match_side_count(self.int2, lengths1, tol=tol)

    def _match_side_count(self, inter:Interface, to_add, tol=0.1):
        """Add the vertices at given location to the edge sequence in a given interface

        Parameters:
            * inter -- interface to modify
            * to_add -- the length of segements to be projects onto the edge sequence in the inter
            * tol -- the proximity of vertices when they can be regarded as the same vertex.  
                    NOTE: tol should be shorter then the smallest expected edge
        """

        # NOTE Edge sequences to subdivide might be disconnected 
        # (even belong to different panels), so we need to subdivide per edge

        # Go over the edges keeping track of their fractions
        add_id, in_id = 0, 0
        covered_init, covered_added = 0, 0
        while in_id < len(inter.edges) and add_id < len(to_add):
            next_init = covered_init + inter.projecting_edges()[in_id].length()  # projected edges though
            next_added = covered_added + to_add[add_id]
            if close_enough(next_init, next_added, tol):
                # the vertex exists, skip
                in_id += 1
                add_id += 1
                covered_init, covered_added = next_init, next_added
            elif next_init < next_added:
                # add on the next step
                in_id += 1
                covered_init = next_init
            else:
                # add a vertex to the edge at the new location
                # Eval on projected edge
                projected_edge = inter.projecting_edges()[in_id]
                new_v_loc = projected_edge.length() - (next_init - next_added)
                frac = new_v_loc / projected_edge.length()
                base_edge = inter.edges[in_id]

                # add with the same fraction to the base edge
                subdiv = EdgeSeqFactory.from_fractions(base_edge.start, base_edge.end, [frac, 1 - frac])

                inter.panel[in_id].edges.substitute(base_edge, subdiv)  # Update the panel
                inter.edges.substitute(base_edge, subdiv)  # interface
                inter.panel.insert(in_id, inter.panel[in_id])  # update panel correspondance

                # next step
                in_id += 1
                add_id += 1
                covered_init += subdiv[0].length()
                covered_added = next_added

        if add_id != len(to_add):
            raise RuntimeError(f'{self.__class__.__name__}::Error::Projection failed')
                

    def assembly(self):
        """Produce a stitch that connects two interfaces
        """
        if not self.isMatching():
            raise RuntimeError(f'{self.__class__.__name__}::Error::Stitch sides do not matched!!')

        stitches = []
        swap = not self.isTraversalMatching()  # traverse edge sequences correctly

        for i, j in zip(range(len(self.int1.edges)), range(len(self.int2.edges) - 1, -1, -1) if swap else range(len(self.int2.edges))):
            stitches.append([
                {
                    'panel': self.int1.panel[i].name,  # corresponds to a name. 
                                            # Only one element of the first level is expected
                    'edge': self.int1.edges[i].geometric_id
                },
                {
                    'panel': self.int2.panel[j].name,
                    'edge': self.int2.edges[j].geometric_id
                }
            ])
        return stitches


class Stitches():
    """Describes a collection of StitchingRule objects
        Needed for more compact specification and evaluation of those rules
    """
    def __init__(self, *rules) -> None:
        """Rules -- any number of tuples of two interfaces (Interface, Interface) """

        self.rules = [StitchingRule(int1, int2) for int1, int2 in rules]

    def append(self, pair):  # TODO two parameters explicitely rather then "pair" object?
        self.rules.append(StitchingRule(*pair))
    
    def assembly(self):
        stitches = []
        for rule in self.rules:
            stitches += rule.assembly()
        return stitches