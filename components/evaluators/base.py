import fitz
import base64
import os
from config.paths import ProjectPaths

class EvaluationStep:
    """Abstract base class for all isolated evaluation pipeline steps."""
    def run(self, pdf_path: str, client, model_name: str, anchor_context: str) -> dict:
        raise NotImplementedError("Each evaluation strategy must implement the run method.")
    

    def prepare_step_anchors(self, anchor_data: dict, target_categories: list, requires_visuals: bool = False) -> dict:
        if not anchor_data or not target_categories:
            return {}
            
        compiled_anchors = {}
        selected_rejects = {}
        selected_accepted = []
        
        for id, data in anchor_data.items():
            if data.get('is_desk_reject') == 1:
                category = data.get('rejection_category')
                if category in target_categories and category not in selected_rejects:
                    selected_rejects[category] = (id, data)
            else:
                selected_accepted.append((id, data))
        
        final_anchors = list(selected_rejects.values()) + selected_accepted
        
        for id, data in final_anchors: 
            fragment = f"=== ANCHOR CASE: {id} (VERDICT: {data['is_desk_reject']}) ===\n"
            if data['is_desk_reject'] == 1:
                fragment += f"REASON: {data.get('rejection_category')}\n"
            
            raw_text = data.get('parsed_text', '')
            if 'raw_comments' in data and data['raw_comments'] != "None":
                fragment += f"SPECIFIC VIOLATION FOUND: {data['raw_comments']}\n"
            
            front_matter = raw_text[:2000]
            ref_index = raw_text.lower().rfind("references")
            back_matter = raw_text[ref_index:ref_index + 3000] if ref_index != -1 else raw_text[-3000:]
            
            fragment += f"[START OF PAPER FRAGMENT]\n{front_matter}\n[... TRUNCATED BODY ...]\n{back_matter}\n[END OF PAPER FRAGMENT]\n"
            fragment += "=========================================\n\n"

            visuals = {}
            if requires_visuals:
                forum_id = data.get('forum_id')

                paths = ProjectPaths()
                anchor_pdf_path = paths.get_anchor_pdf_path(forum_id)

                if anchor_pdf_path and os.path.exists(anchor_pdf_path):
                    try:
                        visuals = {
                            "page_1": self.get_page_as_base64_image(anchor_pdf_path, page_num=1),
                            "page_9": self.get_page_as_base64_image(anchor_pdf_path, page_num=9),
                            "page_10": self.get_page_as_base64_image(anchor_pdf_path, page_num=10)
                        }
                    except Exception as e:
                        print(f"Skipping visual rendering for anchor {id}: {e}")
            
            compiled_anchors[id] = {
                "is_desk_reject": data['is_desk_reject'],
                "rejection_category": data.get('rejection_category'),
                "text_fragment": fragment,
                "visual_anchors": visuals
            }
        
        return compiled_anchors
    
    @staticmethod
    def get_page_as_base64_image(pdf_path: str, page_num: int, zoom: float = 0.8) -> str: 
        """Renders a specific 1-based page number from a PDF into a crisp Base64 PNG."""
        doc = fitz.open(pdf_path)
        if page_num > doc.page_count:
            doc.close()
            # raise IndexError(f"Requested page {page_num}, but paper only has {doc.page_count} pages.")
            print(f"Requested page {page_num}, but paper only has {doc.page_count} pages.")
            return None
        
        page = doc.load_page(page_index := page_num - 1) # fits page indexing starts at 0 afaik
        matrix = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=matrix)
        image_bytes = pix.tobytes("png")
        doc.close()
        
        return base64.b64encode(image_bytes).decode("utf-8")