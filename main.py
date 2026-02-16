import sys
import os

# Add the current directory to sys.path so we can import src
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.main import main

if __name__ == "__main__":
    main()
