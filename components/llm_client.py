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

    def __init__(self, model_name: str = "google/gemini-3.5-flash"):
        
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

    def evaluate_paper(self ,file_path : str ) -> dict:

        print("Successfully built the anchor data...")

        # file_path = self.paths.get_evaluation_pdf_path(paper_forum_id, status_folder)
        
        is_desk_reject = 0
        rejection_categories = []
        detailed_justifications = []
        detected_external_links = []
        
        for step in self.pipeline:
            step_name = step.__class__.__name__
            print(f"[Executing Pipeline Step: {step_name}]")
            
            # Execute the evaluation step in the pipeline
            verdict = step.run(file_path, self.client, self.model_name, self.anchor_data)

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
    gemini_flash_2_5 = "google/gemini-2.5-flash"
    gemini_flash_3_5 = "google/gemini-3.5-flash"
    gpt_mini  = "openai/gpt-4o-mini"

    try:
        evaluator = ScreeningLLMClient(model_name=gemini_flash_3_5)

        evaluator.load_anchors(labels_json_path=evaluator.paths.manual_dataset_json)
        file_path = evaluator.paths.get_evaluation_pdf_path('DRWSVEmGt1', 'desk-rejects')
        print(evaluator.evaluate_paper(file_path))
        evaluator.print_usage_report()

    except ValueError as err:
        print(f"Failed to bootstrap pipeline: {err}")