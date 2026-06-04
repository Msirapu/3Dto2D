# ai/agent.py
import os
import json
from google import genai
from ai.prompts import SYSTEM_PROMPT

class CADMetadataAgent:
    def __init__(self):
        # Initializes the standard Google GenAI client using environment keys
        # Make sure you have run: export GEMINI_API_KEY="your-key" (or set it in Windows Env)
        self.client = genai.Client()
        self.model_name = "gemini-2.5-flash"

    def analyze_part(self, raw_geometry_summary):
        """
        Sends the geometric data summary to the LLM to get manufacturing intent.
        
        raw_geometry_summary: dict containing raw metrics (e.g., bounding box dims, hole counts)
        """
        # Format the technical payload for the model
        user_content = f"""
        Analyze the following extracted geometric parameters from a STEP model:
        {json.dumps(raw_geometry_summary, indent=2)}
        
        Determine the manufacturing requirements and return the requested structural JSON.
        """
        
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=user_content,
                config={
                    "system_instruction": SYSTEM_PROMPT,
                    "response_mime_type": "application/json"
                }
            )
            
            # Safely parse the clean structural JSON string returned by the model
            return json.loads(response.text)
            
        except Exception as e:
            print(f"[AI Agent Error] Failed to generate or parse response: {e}")
            # Fallback standard engineering boilerplate if the API connection or parse fails
            return {
                "part_type": "UNKNOWN_MECHANICAL_COMPONENT",
                "manufacturing_notes": [
                    "DEBURR ALL SHARP EDGES",
                    "DIMENSIONS APPLY AFTER SURFACE TREATMENT",
                    "STANDARD TOLERANCE PER ISO 2768-m"
                ],
                "dimensioning_strategy": {
                    "critical_views": ["front"],
                    "annotation_focus": "Standard fallback envelope dimensions"
                }
            }