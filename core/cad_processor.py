# core/cad_processor.py
"""
CAD Processor — STEP loader and 2D orthographic projection engine.

Critical fix: HLRBRep_HLRToShape exposes SEVEN distinct edge compounds.
Previous versions only read VCompound (sharp visible) + HCompound (sharp hidden).
That means cylindrical silhouettes (OutLineVCompound), smooth tangent edges
(Rg1LineVCompound), and sewn edges (RgNLineVCompound) were all silently dropped,
causing any rounded or cylindrical feature to vanish in profile views.

This version extracts all visible compounds and marks them correctly.

Coordinate system:
    X → right,  Y → depth (into screen),  Z → up

3rd-angle projection axes (normal, xdir → sheet-X):
    FRONT  normal=(0,-1,0)  xdir=(1,0,0)  → sheet-X=worldX, sheet-Y=worldZ
    TOP    normal=(0, 0,1)  xdir=(1,0,0)  → sheet-X=worldX, sheet-Y=worldY
    RIGHT  normal=(1, 0,0)  xdir=(0,1,0)  → sheet-X=worldY, sheet-Y=worldZ
"""

import cadquery as cq
import math

from OCP.HLRBRep    import HLRBRep_Algo, HLRBRep_HLRToShape
from OCP.HLRAlgo    import HLRAlgo_Projector
from OCP.gp         import gp_Pnt, gp_Dir, gp_Ax2
from OCP.TopExp     import TopExp_Explorer
from OCP.TopAbs     import TopAbs_EDGE
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.GeomAbs    import GeomAbs_Line, GeomAbs_Circle
from OCP.TopoDS     import TopoDS
from OCP.TopAbs import TopAbs_FACE
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import (
    GeomAbs_Plane,
    GeomAbs_Cylinder,
    GeomAbs_Cone,
    GeomAbs_Sphere,
    GeomAbs_Torus,
    GeomAbs_BSplineSurface
)
from OCP.TopoDS import TopoDS_Face
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.GProp import GProp_GProps


class CADProcessor:

    def __init__(self, step_path):
        try:
            self.workplane = cq.importers.importStep(step_path)
            self.shape     = self.workplane.val().wrapped
        except Exception as e:
            raise ValueError(f"Unable to load STEP file: {e}")

    # ── Public ────────────────────────────────────────────────────────────────

    def extract_surface_metadata(self):

        surfaces = []

        exp = TopExp_Explorer(self.shape, TopAbs_FACE)

        while exp.More():

            face = TopoDS.Face_s(exp.Current())

            adaptor = BRepAdaptor_Surface(face)

            surface_type = adaptor.GetType()

            props = GProp_GProps()
            BRepGProp.SurfaceProperties_s(face, props)
            area = props.Mass()
        

            face_data = {
                "surface_type": str(surface_type),
                "area": area
            }

            # PLANAR FACE
            if surface_type == GeomAbs_Plane:

                plane = adaptor.Plane()

                face_data["type"] = "plane"

                face_data["normal"] = (
                    plane.Axis().Direction().X(),
                    plane.Axis().Direction().Y(),
                    plane.Axis().Direction().Z()
                )

            # CYLINDRICAL FACE
            elif surface_type == GeomAbs_Cylinder:

                cyl = adaptor.Cylinder()

                face_data["type"] = "cylinder"

                face_data["radius"] = cyl.Radius()

                face_data["axis"] = (
                    cyl.Axis().Direction().X(),
                    cyl.Axis().Direction().Y(),
                    cyl.Axis().Direction().Z()
                )

            # CONICAL FACE
            elif surface_type == GeomAbs_Cone:

                cone = adaptor.Cone()

                face_data["type"] = "cone"

                face_data["semi_angle"] = cone.SemiAngle()

            # SPLINE / FREEFORM
            elif surface_type == GeomAbs_BSplineSurface:

                face_data["type"] = "bspline"

            else:
                face_data["type"] = "other"

            surfaces.append(face_data)

            exp.Next()

        return surfaces
    
    def generate_2d_projections(self):
        """
        Returns dict: view_name → list of edge dicts.
        Each edge dict: {type, pts|(center+radius), hidden}
        """
        # Standard Third-Angle Projection Vector Alignment
        view_axes = {
            # Looking towards +Y: Sheet X = World X, Sheet Y = World Z
            "front": (gp_Dir(0, -1, 0), gp_Dir(1, 0, 0)),
            
            # Looking down from +Z: Sheet X = World X, Sheet Y = World Y (Inverted to face front)
            "top":   (gp_Dir(0, 0, 1), gp_Dir(1, 0, 0)),
            
            # Looking from +X: Sheet X = World Y, Sheet Y = World Z
            "right": (gp_Dir(1, 0, 0), gp_Dir(0, 1, 0)),
        }

        views  = {name: [] for name in view_axes}
        origin = gp_Pnt(0, 0, 0)

        for view_name, (normal, xdir) in view_axes.items():
            hlr = HLRBRep_Algo()
            hlr.Add(self.shape)
            hlr.Projector(HLRAlgo_Projector(gp_Ax2(origin, normal, xdir)))
            hlr.Update()

            ts = HLRBRep_HLRToShape(hlr)

            # Visible items
            for compound in (
                ts.VCompound(),
                ts.Rg1LineVCompound(),
                ts.RgNLineVCompound(),
                ts.OutLineVCompound(),
            ):
                self._extract_edges(compound, views[view_name], hidden=False)

            # Hidden items 
            for compound in (
                ts.HCompound(),
                ts.Rg1LineHCompound(),
                ts.OutLineHCompound(),
            ):
                self._extract_edges(compound, views[view_name], hidden=True)

            # Post-process Top view orientation to align with Front View coordinate space
            if view_name == "top" and views["top"]:
                for edge in views["top"]:
                    if edge["type"] == "line":
                        p1, p2 = edge["pts"]
                        # Invert Y to correct standard Third-Angle plan-view drift
                        edge["pts"] = ((p1[0], -p1[1]), (p2[0], -p2[1]))
                    elif edge["type"] == "circle":
                        cx, cy = edge["center"]
                        edge["center"] = (cx, -cy)

            if not views[view_name]:
                views[view_name].append(
                    {"type": "line", "pts": ((0, 0), (1, 0)), "hidden": False})

        return views

    # ── Edge extraction ───────────────────────────────────────────────────────

    def _extract_edges(self, compound, out_list, hidden):
        """Walk a TopoDS_Compound and append edge dicts to out_list."""
        if compound.IsNull():
            return

        exp = TopExp_Explorer(compound, TopAbs_EDGE)
        while exp.More():
            edge    = TopoDS.Edge_s(exp.Current())
            adaptor = BRepAdaptor_Curve(edge)
            u1      = adaptor.FirstParameter()
            u2      = adaptor.LastParameter()
            ctype   = adaptor.GetType()

            if ctype == GeomAbs_Line:
                p1 = adaptor.Value(u1)
                p2 = adaptor.Value(u2)
                # Skip degenerate zero-length edges
                if abs(p2.X()-p1.X()) < 1e-6 and abs(p2.Y()-p1.Y()) < 1e-6:
                    exp.Next()
                    continue
                out_list.append({
                    "type":   "line",
                    "pts":    ((p1.X(), p1.Y()), (p2.X(), p2.Y())),
                    "hidden": hidden,
                })

            elif ctype == GeomAbs_Circle:
                circ   = adaptor.Circle()
                centre = circ.Location()
                radius = circ.Radius()
                if radius < 1e-6:
                    exp.Next()
                    continue
                span = abs(u2 - u1)
                if abs(span - 2 * math.pi) < 1e-4:
                    # Complete circle
                    out_list.append({
                        "type":   "circle",
                        "center": (centre.X(), centre.Y()),
                        "radius": radius,
                        "hidden": hidden,
                    })
                else:
                    # Partial arc → polyline
                    self._discretise(adaptor, u1, u2, out_list, hidden, 48)

            else:
                # Ellipses, splines, B-splines → dense polyline
                self._discretise(adaptor, u1, u2, out_list, hidden, 64)

            exp.Next()

    def _discretise(self, adaptor, u1, u2, out_list, hidden, segments=48):
        """Approximate a curve as a chain of line segments."""
        pts = []
        for i in range(segments + 1):
            u = u1 + (u2 - u1) * i / segments
            p = adaptor.Value(u)
            pts.append((p.X(), p.Y()))

        for i in range(len(pts) - 1):
            dx = abs(pts[i+1][0] - pts[i][0])
            dy = abs(pts[i+1][1] - pts[i][1])
            if dx < 1e-6 and dy < 1e-6:
                continue   # skip degenerate micro-segments
            out_list.append({
                "type":   "line",
                "pts":    (pts[i], pts[i+1]),
                "hidden": hidden,
            })
    
    