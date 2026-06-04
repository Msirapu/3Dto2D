# generate_valve_body.py
import os

try:
    import cadquery as cq
except ImportError:
    print("❌ Error: cadquery is not installed in this environment.")
    print("Please run: pip install cadquery")
    exit(1)

def create_valve_body_test_part():
    print("🛠️  Generating 3D Cylinder Valve Body...")
    
    # Parameters for the stepped cylinder
    flange_diameter = 80.0
    flange_thickness = 12.0
    body_diameter = 45.0
    total_length = 75.0
    thru_hole_diameter = 25.0
    
    # 1. Create the main cylindrical body shaft
    body = cq.Workplane("XY").circle(body_diameter / 2).extrude(total_length)
    
    # 2. Add a wide flange at the base (offset from the bottom face)
    body = (
        body.faces("<Z")
        .workplane()
        .circle(flange_diameter / 2)
        .extrude(flange_thickness)
    )
    
    # 3. Drill a main fluid passage through-hole down the entire center axis
    body = (
        body.faces(">Z")
        .workplane()
        .hole(thru_hole_diameter)
    )
    
    # 4. Create a 4-hole circular bolt pattern on the flange face
    # Bolt Circle Diameter (BCD) = 64mm, Hole Size = 6mm
    body = (
        body.faces("<Z")
        .workplane()
        .polarArray(64.0 / 2, 0.0, 360.0, 4)  # radius, startAngle, totalAngle, count
        .hole(6.0)
    )
    
    # Define save path
    output_dir = r"C:\Users\msira\Desktop\gemini"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "Valve_Body_02.STEP")
    
    # Export the STEP geometry
    print(f"📦 Exporting solid geometry to STEP format...")
    cq.exporters.export(body, output_path)
    print(f"🚀 SUCCESS: New test file ready at:\n👉 {output_path}")

if __name__ == "__main__":
    create_valve_body_test_part()