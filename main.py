from dotenv import load_dotenv
import os
import sys

# this code was partially generated with the assistance of GitHub Copilot and Google Gemini, and thoroughly reviewed by me

load_dotenv() 

gemini_key = os.getenv("GEMINI_API_KEY")

sys.path.append(os.path.join(os.path.dirname(__file__), 'components'))

from components.ingestion import run_ingestion
from components.preprocessing import build_dataset

def main():
    UNIQUE_FLAG = 0
    run_ingestion(UNIQUE_FLAG)

    build_dataset()


if __name__ == "__main__":
    main()