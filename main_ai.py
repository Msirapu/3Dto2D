# main_ai.py
import os
from core.cad_processor import CADProcessor
from core.drawing_generator import DrawingGenerator
from ai.agent import CADMetadataAgent
from core.feature_extractor import FeatureExtractor

def run_ai_pipeline(step_path):
    print(f"=== STARTING AI-DRIVEN CAD PIPELINE ===")
    print(f"[Step 1/4] Processing physical 3D STEP geometry...")
    processor = CADProcessor(step_path)
    views_data = processor.generate_2d_projections()
    
# ============================================
# Advanced surface + feature extraction
# ============================================

    surface_metadata = processor.extract_surface_metadata()

    extractor = FeatureExtractor(
    surface_metadata,
    views_data
    )

    feature_metadata = extractor.extract_all_features()

    # Add source file context
    feature_metadata["source_file"] = os.path.basename(step_path)
    
    print(f"[Step 2/4] Consulting AI Agent for manufacturing strategy...")
    ai_agent = CADMetadataAgent()
    ai_decisions = ai_agent.analyze_part(feature_metadata)
    
    print(f"\n💡 AI Identified Part Type: {ai_decisions.get('part_type')}")
    print(f"📋 AI Generated Notes for Title Block:")
    for note in ai_decisions.get("manufacturing_notes", []):
        print(f"  - {note}")
        
    print(f"\n[Step 3/4] Compiling drafting geometries via classical engine...")
    generator = DrawingGenerator()
    generator.create_sheet_layout()
    
    # Passes the flat clean views dictionary directly to the drawing generator!
    generator.populate_views(views_data)
    
    # Inject the AI's semantic notes straight into the technical print layout dynamically!
    generator.write_manufacturing_notes(ai_decisions.get("manufacturing_notes", []))
    
    # Pass the AI-generated title directly to the title block method!
    generator.populate_title_block(
        filename=os.path.basename(step_path), 
        custom_title=ai_decisions.get("engineered_title")
    )
    
    print(f"[Step 4/4] Serializing final blueprint...")
    output_name = f"AI_OUTPUT_{os.path.splitext(os.path.basename(step_path))[0]}.dxf"
    generator.save(output_name)
    print(f"🚀 SUCCESS! Intelligent technical blueprint saved as: {output_name}\n")

if __name__ == "__main__":
    target_part = r"Usage: python main.py path/to/model.stp"
    
    if os.path.exists(target_part):
        run_ai_pipeline(target_part)
    else:
        print(f"Target model not found at: {target_part}. Please check your path.")