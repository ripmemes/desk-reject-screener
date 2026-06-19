import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from config.prompts import *
from evaluators.page_limit import VisualBoundaryCheck
from evaluators.layout import LayoutCheck
from evaluators.text import TextualCheck
from evaluators.base import EvaluationStep
from config.paths import ProjectPaths

# this code was partially generated with the assistance of GitHub Copilot and Google Gemini, and thoroughly reviewed and adjusted by me.

class ScreeningLLMClient:
    # class to reuse the network connection + track token usage

    def __init__(self, model_name: str = "deepseek/deepseek-v4-flash"):
        
        self.paths = ProjectPaths() 
        load_dotenv(self.paths.dotenv_path)

        api_key = os.getenv("API_KEY")
        if not api_key:
            raise ValueError("API_KEY is missing from the .env file.")

        self.client = OpenAI(base_url="https://openrouter.ai/api/v1"
                            ,api_key=api_key)
        self.model_name = model_name
        
        self.pipeline = [ 
            VisualBoundaryCheck(),
            LayoutCheck(),
            TextualCheck()
        ]
        # Anchor dataset dictionary acting as the in-context evaluation standard
        self.anchor_data = {}
        
        # State counters to keep track of total token investments across a batch run
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def load_anchors(self, labels_json_path: str):
        """
        Loads the labeled dataset JSON file
        
        Args:
            labels_json_path: Path to the JSON map of paper IDs to their ground truth classifications.
        """
        if not os.path.exists(labels_json_path):
            print(f"Warning: Anchor label file not found at {labels_json_path}. Proceeding without anchors.")
            return

        with open(labels_json_path, 'r', encoding='utf-8') as f:
            self.anchor_data = json.load(f)
            print("Anchors loaded succesfully...")
        

    def _build_anchor_instruction_string(self) -> str:
        if not self.anchor_data:
            return "No examples provided for this run."
            
        anchor_str = "Use these verified historical benchmarks. Verdicts: 0=Accepted, 1=Desk Reject:\n\n"
        
        for id, data in list(self.anchor_data.items())[:3]: 
            anchor_str += f"=== ANCHOR CASE: {id} (VERDICT: {data['is_desk_reject']}) ===\n"
            anchor_str += f"REASON: {data['rejection_category']}\n"
            
            raw_text = data.get('parsed_text', '')

            if 'raw_comments' in data and data['raw_comments'] != "None":
                anchor_str += f"SPECIFIC VIOLATION FOUND: {data['raw_comments']}\n"
            
            # Extract the structural fragments
            front_matter = raw_text[:2000] # First ~500 words for anonymity checking
            
            # Find references to check page-limit behavior
            ref_index = raw_text.lower().rfind("references")
            back_matter = raw_text[ref_index:ref_index + 3000] if ref_index != -1 else raw_text[-3000:]
            
            anchor_str += f"[START OF PAPER FRAGMENT]\n{front_matter}\n[... TRUNCATED BODY ...]\n{back_matter}\n[END OF PAPER FRAGMENT]\n"
            
            # Dynamically append the base64 image string directly into the text block
            anchor_pdf_path = data.get('pdf_path')
            if anchor_pdf_path and os.path.exists(anchor_pdf_path):
                try:
                    b64_img = EvaluationStep.get_page_as_base64_image(anchor_pdf_path, page_num=9)
                    anchor_str += f"[VISUAL ANCHOR PAGE 9 DATA URI]: data:image/png;base64,{b64_img}\n"
                except Exception as e:
                    print(f"Skipping visual rendering for anchor {id}: {e}")
                    
            anchor_str += "=========================================\n\n"
        
        return anchor_str


    def evaluate_paper(self, paper_forum_id: str) -> dict:
       
        anchor_context = self._build_anchor_instruction_string()
        print("Successfully built the anchor instruction string...")

        file_path = self.paths.get_evaluation_pdf_path(paper_forum_id, status_folder="accepted")
        
        is_desk_reject = 0
        rejection_categories = []
        detailed_justifications = []
        detected_external_links = []
        
        for step in self.pipeline:
            step_name = step.__class__.__name__
            print(f"[Executing Pipeline Step: {step_name}]")
            
            # Execute the evaluation step in the pipeline
            verdict = step.run(file_path, self.client, self.model_name, anchor_context)

            if "usage" in verdict:
                self.total_input_tokens += verdict["usage"].get("input_tokens", 0)
                self.total_output_tokens += verdict["usage"].get("output_tokens", 0)
            
            if verdict.get("is_desk_reject") == 1:
                is_desk_reject = 1
                if verdict.get("rejection_category"):
                    rejection_categories.append(verdict.get("rejection_category"))

            justification = verdict.get('detailed_justification')
            if not justification or justification.lower().strip() in ["none", "null", "none."]:
                justification = "Compliant. No violations detected."
                    
            detailed_justifications.append(f"[{step_name}]: {justification}")
            
            if "detected_external_links" in verdict:
                detected_external_links.extend(verdict.get("detected_external_links", []))

        return {
            "is_desk_reject": is_desk_reject,
            "rejection_category": ", ".join(rejection_categories) if rejection_categories else None,
            "detailed_justification": " | ".join(detailed_justifications),
            "detected_external_links": list(set(detected_external_links))
        }

    def print_usage_report(self):
        """Prints the accumulated token statistics."""
        print("\n--- API COMPUTE USAGE REPORT ---")
        print(f"Total Input Tokens Tracked: {self.total_input_tokens}")
        print(f"Total Output Tokens Tracked: {self.total_output_tokens}")
        print("---------------------------------")


if __name__ == "__main__":
    print("Testing the anchor-driven screening class...")
    deepseek = "deepseek/deepseek-v4-flash"
    gemini_flash = "google/gemini-2.5-flash"
    try:
        evaluator = ScreeningLLMClient(model_name=gemini_flash)

        evaluator.load_anchors(labels_json_path=evaluator.paths.dataset_json)
        

        print(evaluator.evaluate_paper('7cEMkTu7Lf'))
        evaluator.print_usage_report()

    except ValueError as err:
        print(f"Failed to bootstrap pipeline: {err}")