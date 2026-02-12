import subprocess
import sys
import os

def main():
    """ Runs the Trading Dashboard (py_dashboard) using Streamlit. """
    script_path = os.path.join("py_dashboard", "run_dashboard.py")
    
    if not os.path.exists(script_path):
        print(f"Error: Could not find {script_path}")
        sys.exit(1)
        
    print("🚀 Starting Trading Dashboard...")
    try:
        # We run streamlit as a subprocess
        subprocess.run(["streamlit", "run", script_path], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error: Streamlit failed with exit code {e.returncode}")
        sys.exit(e.returncode)
    except FileNotFoundError:
        print("Error: 'streamlit' command not found. Please install it with 'pip install streamlit'.")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n👋 Dashboard stopped.")

if __name__ == "__main__":
    main()
