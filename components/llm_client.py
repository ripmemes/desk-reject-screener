import os
import json
from openai import OpenAI
from dotenv import load_dotenv

from preprocessing import extract_pdf_data # reuse some methods

# this code was partially generated with the assistance of GitHub Copilot and Google Gemini, and thoroughly reviewed and adjusted by me.

class ScreeningLLMClient:
    # class to reuse the network connection + track token usage

    def __init__(self, model_name: str = "deepseek/deepseek-v4-flash"):
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        dotenv_path = os.path.join(script_dir, '..', '.env')
        load_dotenv(dotenv_path)

        api_key = os.getenv("API_KEY")
        if not api_key:
            raise ValueError("API_KEY is missing from the .env file.")

        self.client = OpenAI(base_url="https://openrouter.ai/api/v1"
                            ,api_key=api_key)
        self.model_name = model_name
        
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
        
        # Limit to a maximum of 3 key anchors to save tokens
        for id, data in list(self.anchor_data.items())[:3]: 
            anchor_str += f"=== ANCHOR CASE: {id} (VERDICT: {data['is_desk_reject']}) ===\n"
            anchor_str += f"REASON: {data['rejection_category']}\n"
            
            raw_text = data.get('parsed_text', '')
            
            # Extract the structural fragments
            front_matter = raw_text[:2000] # First ~500 words for anonymity checking
            
            # Find references to check page-limit behavior
            ref_index = raw_text.lower().rfind("references")
            back_matter = raw_text[ref_index:ref_index + 3000] if ref_index != -1 else raw_text[-3000:]
            
            anchor_str += f"[START OF PAPER FRAGMENT]\n{front_matter}\n[... TRUNCATED BODY ...]\n{back_matter}\n[END OF PAPER FRAGMENT]\n"
            anchor_str += "=========================================\n\n"
        
        return anchor_str

    def evaluate_paper(self, paper_forum_id: str) -> dict:
        """
        Pipes the raw text to the LLM alongside the loaded anchor data, 
        forcing a strict JSON response structure.
        """
        anchor_context = self._build_anchor_instruction_string()
        print("Successfully built the anchor instruction string...")

        system_prompt = (
            "You are a strict, algorithmic screening assistant running initial checks on conference submissions.\n"
            "Your task is to analyze the text and output a valid JSON object matching the following fields:\n\n"
            "{\n"
            "  \"is_desk_reject\": int ( either 0 or 1 ),\n"
            "  \"rejection_category\": string or null (Choose from: 'Over-length', 'Anonymity_Violation', 'Formatting', 'Hallucinated / Malicious Citations', 'Malformed / Broken Bibliography', 'Scientific Integrity', 'Unclassified/Other' ),\n"
            "  \"detailed_justification\": string (Step-by-step evidence string showing exactly how you made the check),\n"
            "  \"detected_external_links\": list of strings (All raw project URLs found inside the body text)\n"
            "}\n\n"
            "Enforce these checks closely:\n"
            "- PAGE LIMIT: Locate structural references headers like 'References' or 'Bibliography'. Look at the closest "
            "surrounding '--- PAGE X ---' markers. If main contents extend past the page limit boundaries, flag it as 'Over-length'.\n"
            "- ANONYMITY: Find unblinded source code links, repositories, or landing profiles containing real author identities.\n\n"
            f"{anchor_context}\n\n"
            "Compare the target paper against these baseline anchors. Return ONLY the strict JSON object. No markdown wrappers, no explanations."
        )

        script_dir = os.path.dirname(os.path.abspath(__file__))
        target_dir = os.path.join(script_dir,"..","data","to_evaluate")
        file_path =  os.path.join(target_dir,f"{paper_forum_id}.pdf")
        raw_text ,_ = extract_pdf_data(file_path)
        

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Analyze this parsed target submission:\n\n{raw_text}"}
                ],
                response_format={"type": "json_object"},
                temperature=0.0 # supposedly makes the model more deterministic.
            )
            
            if response.usage:
                self.total_input_tokens += response.usage.prompt_tokens
                self.total_output_tokens += response.usage.completion_tokens

            return json.loads(response.choices[0].message.content)

        except Exception as e:
            return {
                "is_desk_reject": 0,
                "rejection_category": "API_EXECUTION_ERROR",
                "detailed_justification": f"exception detected: {str(e)}",
                "detected_external_links": []
            }

    def print_usage_report(self):
        """Prints the accumulated token statistics."""
        print("\n--- API COMPUTE USAGE REPORT ---")
        print(f"Total Input Tokens Tracked: {self.total_input_tokens}")
        print(f"Total Output Tokens Tracked: {self.total_output_tokens}")
        print("---------------------------------")


if __name__ == "__main__":
    print("Testing the anchor-driven screening class...")
    try:
        evaluator = ScreeningLLMClient(model_name="deepseek/deepseek-v4-flash")

        script_dir = os.path.dirname(os.path.abspath(__file__))
        dataset_path = os.path.join(script_dir, "..", "data", "processed", "labeled_dataset.json")
        evaluator.load_anchors(labels_json_path=dataset_path)
        

        print(evaluator.evaluate_paper('DRWSVEmGt1'))
        evaluator.print_usage_report()

    except ValueError as err:
        print(f"Failed to bootstrap pipeline: {err}")