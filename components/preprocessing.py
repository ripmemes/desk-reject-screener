import os
import json
import fitz  

script_dir = os.path.dirname(__file__)

# this code was partially generated with the assistance of GitHub Copilot and Google Gemini, and thoroughly reviewed by me

DESK_REJECTS_FILE = os.path.join(script_dir,"..", "data","raw","desk-rejects","desk_rejects.json")
ACCEPTED_PAPERS_FILE = os.path.join(script_dir,"..","data","raw","accepted", "accepted_papers.json")
PROCESSED_DATA_DIR = os.path.join(script_dir, "..", "data", "processed")
OUTPUT_DATASET = os.path.join(PROCESSED_DATA_DIR, "labeled_dataset.json")


os.makedirs(PROCESSED_DATA_DIR, exist_ok=True)

# A function to extract text and page count from a PDF file using PyMuPDF (fitz).
def extract_pdf_data(pdf_path):
    if not os.path.exists(pdf_path):
        return None, 0
    
    try:
        doc = fitz.open(pdf_path)
        page_count = doc.page_count
        text = ""
        for page in doc:
            text += page.get_text("text") + "\n"
        doc.close()
        return text, page_count
    except Exception as e:
        print(f"Error reading {pdf_path}: {e}")
        return None, 0
    

# A simple heuristic to group raw comments into standardized categories.
def categorize_rejection(comments):
    comments_lower = comments.lower()
    if "page" in comments_lower or "length" in comments_lower or "limit" in comments_lower or "format" in comments_lower:
        return "Formatting/Length"
    elif "blind" in comments_lower or "anonym" in comments_lower or "author" in comments_lower or "identif" in comments_lower:
        return "Anonymity Violation"
    elif "scope" in comments_lower or "track" in comments_lower:
        return "Out of Scope"
    elif "plagiar" in comments_lower or "overlap" in comments_lower or "reference" in comments_lower or "fake" in comments_lower:
        return "Scientific Integrity"
    else:
        return "Other / Quality"

def load_json(filepath):
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def build_dataset():
    desk_rejects = load_json(DESK_REJECTS_FILE)
    accepted_papers = load_json(ACCEPTED_PAPERS_FILE)
    
    final_dataset = []

    for reason_key, paper_data in desk_rejects.items():
        forum_id = paper_data.get('forum_id')
        pdf_path = os.path.join(script_dir, "..", "data", "raw", "desk-rejects", f"{forum_id}.pdf")
        
        parsed_text, page_count = extract_pdf_data(pdf_path)
        
        if parsed_text:
            final_dataset.append({
                "forum_id": forum_id,
                "title": paper_data.get("title"),
                "is_desk_reject": 1,
                "rejection_category": categorize_rejection(paper_data.get("comments")),
                "raw_comments": paper_data.get("comments"),
                "page_count": page_count,
                "parsed_text": parsed_text
            })

    for note_id, paper_data in accepted_papers.items():
        forum_id = paper_data.get('forum_id')
        pdf_path = os.path.join(script_dir, "..", "data", "raw", "accepted", f"{forum_id}.pdf")
        
        parsed_text, page_count = extract_pdf_data(pdf_path)
        
        if parsed_text:
            final_dataset.append({
                "forum_id": forum_id,
                "title": paper_data.get("title"),
                "is_desk_reject": 0,
                "rejection_category": "None",
                "raw_comments": "None",
                "page_count": page_count,
                "parsed_text": parsed_text
            })

    with open(OUTPUT_DATASET, 'w', encoding='utf-8') as f:
        json.dump(final_dataset, f, ensure_ascii=False, indent=4)
        
    print(f"Success! Processed {len(final_dataset)} total papers.")

if __name__ == "__main__":
    build_dataset()