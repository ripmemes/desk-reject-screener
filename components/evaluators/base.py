import fitz
import base64

class EvaluationStep:
    """Abstract base class for all isolated evaluation pipeline steps."""
    def run(self, pdf_path: str, client, model_name: str, anchor_context: str) -> dict:
        raise NotImplementedError("Each evaluation strategy must implement the run method.")
    
    @staticmethod
    def get_page_as_base64_image(pdf_path: str, page_num: int, zoom: float = 2.0) -> str: 
        """Renders a specific 1-based page number from a PDF into a crisp Base64 PNG."""
        doc = fitz.open(pdf_path)
        if page_num > doc.page_count:
            doc.close()
            raise IndexError(f"Requested page {page_num}, but paper only has {doc.page_count} pages.")
        
        page = doc.load_page(page_index := page_num - 1)
        matrix = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=matrix)
        image_bytes = pix.tobytes("png")
        doc.close()
        
        return base64.b64encode(image_bytes).decode("utf-8")