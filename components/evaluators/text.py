import os
import json
from evaluators.base import EvaluationStep
from config.prompts import SYSTEM_PROMPTS

from preprocessing import extract_pdf_data

class TextualCheck(EvaluationStep):
    def run(self, pdf_path: str, client, model_name: str, anchor_data: dict) -> dict:

        step_anchors = self.prepare_step_anchors(
            anchor_data=anchor_data, 
            target_categories=[
                "Scientific Integrity"
            ],
            requires_visuals=False
        )

        final_anchor_string = "Use these verified historical benchmarks. Verdicts: 0=Accepted, 1=Desk Reject:\n\n"

        accepted_papers = [data for id, data in step_anchors.items() if data['is_desk_reject'] == 0]
        rejected_papers = [data for id, data in step_anchors.items() if data['is_desk_reject'] == 1]

        #---- CAP
        accepted_papers = accepted_papers[:25]
        rejected_papers = rejected_papers[:25]

        #----
        
        num_accepted = len(accepted_papers)
        num_rejected = len(rejected_papers)
        max_len = max(num_accepted, num_rejected)


        # for i, reject_data in enumerate(rejected_papers):
        for i in range(max_len):
            if i < len(accepted_papers):
                final_anchor_string += accepted_papers[i]['text_fragment']
            if i < len(rejected_papers):
                reject_data = rejected_papers[i]
            final_anchor_string += reject_data['text_fragment']

        parsed_target_text, _ = extract_pdf_data(pdf_path)
        
        if not parsed_target_text:
            return {
                "is_desk_reject": 0,
                "rejection_category": None,
                "detailed_justification": f"TextualCheck failed to parse PDF text layer for {pdf_path}."
            }
        
        payload_content = (
            f"[HISTORICAL ANCHOR CASES]:\n{final_anchor_string}\n\n"
            f"[TARGET PAPER LAYER TO AUDIT]:\n{parsed_target_text}"
        )

        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPTS['textual_integrity_system']},
                    {"role": "user", "content": payload_content}
                ],
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            result["usage"] = {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens
            }
            return result
        except Exception as e:
            return {
                "is_desk_reject": 0,
                "rejection_category": None,
                "detailed_justification": f"TextualCheck pipeline execution failed: {e}"
            }