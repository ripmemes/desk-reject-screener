import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from config.prompts import *
from evaluators.page_limit import VisualBoundaryCheck
from evaluators.layout import LayoutCheck
from evaluators.text import TextualCheck
from evaluators.anonymity import AnonymityCheck
from evaluators.citation import CitationCheck
from config.paths import ProjectPaths

# this code was partially generated with the assistance of GitHub Copilot and Google Gemini, and thoroughly reviewed and adjusted by the author.

class ScreeningLLMClient:
    # class to reuse the network connection + track token usage

    def __init__(self, model_name: str = "qwen/qwen3.7-plus"):
        
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
            AnonymityCheck(),
            CitationCheck(),
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
        rejection_category = []
        detailed_justifications = []
        detected_external_links = []
        responsible_steps = []

        paper_input_tokens = 0
        paper_output_tokens = 0

        step_usages = {}
        
        for step in self.pipeline:
            step_name = step.__class__.__name__
            print(f"[Executing Pipeline Step: {step_name}]")
            
            # Execute the evaluation step in the pipeline
            try:
                verdict = step.run(file_path, self.client, self.model_name, self.anchor_data)
            except ValueError as err : 
                print(f"Error running Evaluation step {step_name} : {err} , cancelling evaluation")
                return {
                    "is_desk_reject": -1,
                    "rejection_category": [],
                    "detailed_justification": None,
                    "detected_external_links": None,
                    "usage": {
                        "input_tokens": None,
                        "output_tokens": None,
                        "step_usages": None
                    }
                }
            


            if "usage" in verdict:
                in_t = verdict["usage"].get("input_tokens", 0)
                out_t = verdict["usage"].get("output_tokens", 0)
                
                self.total_input_tokens += in_t
                self.total_output_tokens += out_t
                paper_input_tokens += in_t
                paper_output_tokens += out_t

                step_usages[step_name] = {"input_tokens": in_t, "output_tokens": out_t}
            
            if verdict.get("is_desk_reject") == 1:
                is_desk_reject = 1
                if verdict.get("rejection_category"):
                    rejection_category.append(verdict.get("rejection_category"))
                responsible_steps.append(step.__class__.__name__)

            justification = verdict.get('detailed_justification')
            if not justification or justification.lower().strip() in ["none", "null", "none."]:
                justification = "Compliant. No violations detected."
                    
            detailed_justifications.append(f"[{step_name}]: {justification}")
            
            
            if "detected_external_links" in verdict:
                detected_external_links.extend(verdict.get("detected_external_links", []))

        return {
            "is_desk_reject": is_desk_reject,
            "rejection_category": rejection_category,
            "detailed_justification": " | ".join(detailed_justifications),
            "responsible_steps" : responsible_steps,
            "detected_external_links": list(set(detected_external_links)),
            "usage": {
                "input_tokens": paper_input_tokens,
                "output_tokens": paper_output_tokens,
                "step_usages": step_usages
            }
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
    kimi = "moonshotai/kimi-k2.5"
    qwen = "qwen/qwen3.7-plus"
    stepfun = "stepfun/step-3.7-flash" # the cheapest
    try:
        evaluator = ScreeningLLMClient(model_name=qwen)

        evaluator.load_anchors(labels_json_path=evaluator.paths.anchor_dataset_json)
        file_path = evaluator.paths.get_evaluation_pdf_path('s3sdghSQDL', 'desk-rejects')
        print(evaluator.evaluate_paper(file_path))
        evaluator.print_usage_report()

    except ValueError as err:
        print(f"Failed to bootstrap pipeline: {err}")