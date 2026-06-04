# CAD Blueprint Generator — AI-Driven 3D to 2D Engineering Drawing Pipeline

An automated system that converts 3D STEP models into dimensioned 2D engineering drawings using classical CAD geometry engines combined with a Gemini AI agent for manufacturing intelligence.

---

## What It Does

Most CAD-to-drawing workflows require a trained engineer to manually set up views, annotations, and manufacturing notes. This pipeline automates that process end-to-end:

1. Loads a `.stp` / `.step` file
2. Extracts surface geometry and 3D features using OpenCASCADE
3. Runs AI analysis (Gemini 2.5 Flash) to identify the part type and generate manufacturing notes
4. Projects three orthographic views using Hidden Line Removal (HLR)
5. Outputs a dimensioned `.dxf` engineering drawing in third-angle projection

The result is a drawing that matches what a CAD engineer would produce manually — with title block, manufacturing notes, hole callouts, and staircase dimensions — generated in seconds from a raw STEP file.

---

## Results

Two parts were tested. For each: the original STEP model, an engineer-drafted reference drawing, and the system-generated output are shown side by side.

### Part 1

| 3D Model | Engineer Drawing | System Output |
|----------|-----------------|---------------|
| `docs\Part1\3D-1.png` | `docs\Part1\Actual2D-1.png` | `docs\Part1\SysGen2D-1.png` |

### Part 2

| 3D Model | Engineer Drawing | System Output |
|----------|-----------------|---------------|
| `docs\Part2\3D-2.png` | `docs\Part2\Actual2D-2.png` | `docs\Part2\SysGen2D-2.png` |

> DXF files were visualised using [ShareCAD.org](https://sharecad.org) — an open-source DXF viewer — to produce the output images above.

---

## Architecture

```
.
├── main.py                    # Pipeline entry point
│
├── ai/
│   ├── agent.py               # Gemini AI client — sends feature JSON, receives manufacturing decisions
│   └── prompts.py             # System prompt defining the manufacturing engineer persona
│
├── core/
│   ├── cad_processor.py       # STEP loader + HLR projection engine (OpenCASCADE via CadQuery)
│   ├── feature_extractor.py   # Geometric feature analysis: holes, fillets, symmetry, bolt patterns
│   └── drawing_generator.py   # DXF output — sheet layout, views, dimensions, title block
│
└── docs/
    ├── part1/                 # STEP file, 3D image, engineer reference, system DXF + rendered output
    └── part2/
```

### How the pipeline flows

```
STEP file
    │
    ▼
CADProcessor.generate_2d_projections()
    Loads B-Rep solid via CadQuery / OpenCASCADE
    Runs HLR (Hidden Line Removal) algorithm in 3 directions
    Returns front / top / right view edge lists
    │
    ├──► CADProcessor.extract_surface_metadata()
    │       Walks all faces: plane, cylinder, cone, B-spline
    │       Returns type, area, radius, axis per face
    │
    ▼
FeatureExtractor.extract_all_features()
    Detects holes, bolt circle patterns, fillets, symmetry
    Returns structured feature JSON
    │
    ▼
CADMetadataAgent.analyze_part()
    Sends feature JSON to Gemini 2.5 Flash
    Returns: engineered_title, manufacturing_notes,
             inspection_notes, manufacturing_process
    │
    ▼
DrawingGenerator
    Places views in third-angle layout (top above front, right beside front)
    Applies uniform scale-to-fit for A3 sheet
    Draws staircase dimensions, hole leaders, center lines
    Writes title block and manufacturing notes
    Saves .dxf
```

---

## Technical Details

### 3D to 2D Projection

The conversion uses OpenCASCADE's **Hidden Line Removal (HLR)** engine, not a rasterizer or triangle mesh renderer. The 3D solid is a mathematically exact B-Rep (Boundary Representation) object. The HLR algorithm:

- Projects all edges using parallel (orthographic) rays — no perspective distortion
- Classifies every projected edge into one of **7 compounds**: sharp visible, smooth tangent visible, seam visible, silhouette visible, sharp hidden, smooth tangent hidden, silhouette hidden
- Extracting all 7 is critical — cylindrical features are invisible if only sharp edges are read

The three camera directions are defined as explicit vectors:

| View | Normal vector | Sheet X | Sheet Y |
|------|--------------|---------|---------|
| Front | `(0, −1, 0)` | World X | World Z |
| Top | `(0, 0, +1)` | World X | −World Y |
| Right | `(+1, 0, 0)` | World Y | World Z |

The top view Y axis is negated to correct the depth mirroring that occurs in third-angle projection.

### Feature Extraction

`FeatureExtractor` analyses the surface metadata from OpenCASCADE to produce a structured feature profile:

- **Holes** — detected from cylindrical faces with bounded radius
- **Bolt circle candidates** — groups of 4+ holes sharing the same diameter
- **Fillets** — small-radius cylindrical faces (r < 5 mm)
- **Symmetry** — detected by testing whether circle centers mirror across their centroid
- **Machining features** — presence flags for drilled holes and edge blends
- **Surface summary** — count of planes, cylinders, cones, B-spline surfaces

### AI Layer

The feature JSON is sent to Gemini 2.5 Flash with a manufacturing engineer system prompt. The model returns:

```json
{
  "engineered_title": "FLANGED BASE MOUNT BRACKET",
  "manufacturing_notes": ["DEBURR ALL SHARP EDGES", "..."],
  "inspection_notes": ["CHECK HOLE DIAMETER TO ±0.02MM", "..."],
  "manufacturing_process": "CNC MILLING + DRILLING"
}
```

The AI response is injected directly into the DXF title block and notes panel — no manual editing.

---

## Setup

### Prerequisites

- Python 3.10+
- A Gemini API key ([get one here](https://aistudio.google.com/))

### Install dependencies

```bash
pip install cadquery ezdxf google-generativeai
```

> CadQuery installs the OpenCASCADE kernel automatically. On Windows, use the conda install path for reliability:
> ```bash
> conda install -c cadquery -c conda-forge cadquery
> ```

### Set API key

```bash
# Linux / macOS
export GEMINI_API_KEY="your-key-here"

# Windows (Command Prompt)
set GEMINI_API_KEY=your-key-here
```

### Run

Edit the `target_part` path in `main.py` then:

```bash
python main.py
```

Output is saved as `AI_OUTPUT_<partname>.dxf` in the working directory. Open with any DXF viewer — [ShareCAD.org](https://sharecad.org), AutoCAD, FreeCAD, or LibreCAD.

---

## Project Structure in Detail

### `core/cad_processor.py`

Wraps the OpenCASCADE HLR pipeline. Key methods:

- `generate_2d_projections()` — runs HLR for front/top/right views, returns edge dicts `{type, pts|center+radius, hidden}`
- `extract_surface_metadata()` — walks all faces and returns type + geometric properties per face

Curves and splines that cannot be stored as DXF arcs are discretised into 64-segment polylines.

### `core/feature_extractor.py`

Pure Python analysis layer. Takes surface metadata and view edge lists, returns a structured feature profile ready for the AI agent.

### `core/drawing_generator.py`

Produces an A3 landscape DXF using `ezdxf`. Manages:

- Sheet border, title block, notes panel
- Third-angle view placement with scale-to-fit
- Staircase dimension lines with text, hole leaders, center lines
- Separate DXF layers: `GEOMETRY`, `HIDDEN_LINES`, `CENTER_LINES`, `DIMENSIONS`, `NOTES`, `BORDER`

### `ai/agent.py`

Thin wrapper around the Google GenAI client. Sends feature JSON with a structured system prompt and parses the JSON response. Falls back to engineering boilerplate if the API call fails.

---

## Roadmap

The current feature extractor works from projected 2D edges and surface type counts. The next development phase involves richer 3D analysis directly on the B-Rep topology.

**Geometric features**
- Hole diameter distribution and tolerance classification (clearance vs thread vs press fit)
- Bolt circle detection with PCD (Pitch Circle Diameter) calculation
- Fillet and chamfer radius extraction per edge
- Pocket and slot detection from planar face topology
- Mating surface identification (flanges, bosses, ribs) from face normals and adjacency

**Drawing intelligence**
- GD&T annotation — flatness, cylindricity, position callouts derived from feature geometry
- Datum plane detection and automatic datum labelling
- Section view generation for internal features not visible in standard projections
- Weld symbol placement for fabricated assemblies

**AI improvements**
- Part classification model trained on feature vectors (turned / milled / sheet metal / cast)
- Tolerance stack-up analysis from hole patterns and mating features
- Process plan generation: operation sequence, tooling recommendations, fixturing notes

These features require deeper OpenCASCADE topology traversal — specifically the `BRep_Builder`, `TopExp`, and `BRepAlgoAPI` APIs for face adjacency graphs and feature recognition.

---

## Dependencies

| Library | Purpose |
|---------|---------|
| [CadQuery](https://github.com/CadQuery/cadquery) | STEP file loading, wraps OpenCASCADE |
| [OpenCASCADE (OCC)](https://dev.opencascade.org/) | HLR projection engine, B-Rep geometry |
| [ezdxf](https://github.com/mozman/ezdxf) | DXF file generation |
| [Google GenAI SDK](https://pypi.org/project/google-generativeai/) | Gemini 2.5 Flash API client |

---


