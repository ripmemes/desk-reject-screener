from dotenv import load_dotenv
import os

# This automatically searches the root folder for a .env file
load_dotenv() 

# Now your API key is safely loaded into memory
gemini_key = os.getenv("GEMINI_API_KEY")