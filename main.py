from dotenv import load_dotenv
import os
import sys

# this code was partially generated with the assistance of GitHub Copilot and Google Gemini, and thoroughly reviewed by me

load_dotenv() 

gemini_key = os.getenv("GEMINI_API_KEY")

sys.path.append(os.path.join(os.path.dirname(__file__), 'components'))

from components.ingestion import run_ingestion
from components.preprocessing import build_dataset
from components.evaluate import calculate_metrics

def main(): # to test this program, it is better to just run 'python components/evaluate.py', because data is already fetched, and preprocessed
            # the llm verdicts are cached in data/to_evaluate/eval_progress_checkpoint.json, if you want to send requests to the llm again and not use this cached data
            # make sure that file or its content is deleted.
    UNIQUE_FLAG = 0
    run_ingestion(UNIQUE_FLAG)
    build_dataset()
    calculate_metrics() # will evaluate the entire evaluation dataset in the to_evaluate folder
    

if __name__ == "__main__":
    main()