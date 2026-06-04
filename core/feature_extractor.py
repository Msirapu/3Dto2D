import math
from collections import defaultdict

class FeatureExtractor:

    def __init__(self, surface_data, projection_views):

        self.surface_data = surface_data
        self.views = projection_views

    def extract_all_features(self):

        return {
            "holes": self.detect_holes(),
            "hole_patterns": self.detect_hole_patterns(),
            "fillets": self.detect_fillets(),
            "symmetry": self.detect_symmetry(),
            "machining_features": self.detect_machining_features(),
            "surface_summary": self.surface_summary()
        }

    # -----------------------------------------
    # HOLE DETECTION
    # -----------------------------------------

    def detect_holes(self):

        holes = []

        for surf in self.surface_data:

            if surf["type"] == "cylinder":

                radius = surf.get("radius", 0)

                if radius < 1000:

                    holes.append({
                        "diameter": radius * 2,
                        "axis": surf.get("axis")
                    })

        return holes

    # -----------------------------------------
    # BOLT CIRCLE DETECTION
    # -----------------------------------------

    def detect_hole_patterns(self):

        holes = self.detect_holes()

        grouped = defaultdict(list)

        for h in holes:

            dia = round(h["diameter"], 1)

            grouped[dia].append(h)

        patterns = []

        for dia, group in grouped.items():

            if len(group) >= 4:

                patterns.append({
                    "pattern_type": "bolt_circle_candidate",
                    "hole_count": len(group),
                    "diameter": dia
                })

        return patterns

    # -----------------------------------------
    # FILLET DETECTION
    # -----------------------------------------

    def detect_fillets(self):

        fillets = []

        for surf in self.surface_data:

            if surf["type"] == "cylinder":

                r = surf.get("radius", 0)

                if r < 5:

                    fillets.append({
                        "radius": r
                    })

        return fillets

    # -----------------------------------------
    # SYMMETRY DETECTION
    # -----------------------------------------

    def detect_symmetry(self):

        circles = []

        for view in self.views.values():

            for entity in view:

                if entity["type"] == "circle":

                    circles.append(entity)

        if len(circles) < 2:
            return False

        xs = [c["center"][0] for c in circles]

        avg = sum(xs) / len(xs)

        mirrored = 0

        for x in xs:

            if any(abs((2 * avg - x) - x2) < 1e-2 for x2 in xs):

                mirrored += 1

        return mirrored > len(xs) * 0.7

    # -----------------------------------------
    # MACHINING FEATURES
    # -----------------------------------------

    def detect_machining_features(self):

        features = []

        holes = self.detect_holes()

        if holes:
            features.append("drilled_holes")

        fillets = self.detect_fillets()

        if fillets:
            features.append("edge_blends")

        return features

    # -----------------------------------------
    # SURFACE SUMMARY
    # -----------------------------------------

    def surface_summary(self):

        counts = defaultdict(int)

        for surf in self.surface_data:

            counts[surf["type"]] += 1

        return dict(counts)