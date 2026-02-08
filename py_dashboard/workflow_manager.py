import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List
import subprocess
import os

@dataclass
class ProcessResult:
    step_name: str
    success: bool
    output: str
    error: Optional[str] = None

class WorkflowManager:
    """
    Manages the file upload and external script execution workflow.
    Designed to be used within the Streamlit app but decoupled from UI logic.
    """
    
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir.resolve()
        
    def save_uploaded_file(self, file_obj, filename: str) -> Path:
        """
        Saves the uploaded file object (from Streamlit) to the project root.
        Returns the absolute path to the saved file.
        """
        target_path = self.root_dir / filename
        with open(target_path, "wb") as f:
            f.write(file_obj.getbuffer())
        return target_path

    def run_parser(self) -> ProcessResult:
        """
        Triggers 'run_csv_parser.py'. Auto-discovery mode (no args) usually picks up the newest csv.
        Or specifically the just uploaded one if it's new.
        Since run_csv_parser.py auto-discovers if no arg provided, and we just saved a file,
        it should pick it up if it's the newest.
        """
        script_path = self.root_dir / "run_csv_parser.py"
        
        try:
            # We run without arguments to trigger auto-discovery logic of run_csv_parser.py
            # If we want explicit, we need to pass the file path.
            # But the requirement says "trigger scripte", let's be explicit if possible.
            # However, run_csv_parser.py logic is good for finding the csv.
            
            result = subprocess.run(
                [sys.executable, str(script_path)],
                cwd=str(self.root_dir),
                capture_output=True,
                text=True,
                check=False
            )
            
            success = (result.returncode == 0)
            return ProcessResult(
                step_name="CSV Parser",
                success=success,
                output=result.stdout,
                error=result.stderr if not success else None
            )
        except Exception as e:
            return ProcessResult("CSV Parser", False, "", str(e))

    def run_portfolio_history(self) -> ProcessResult:
        """
        Triggers 'run_portfolio_history.py'.
        Captures stdout/stderr.
        """
        script_path = self.root_dir / "run_portfolio_history.py"
        try:
            result = subprocess.run(
                [sys.executable, str(script_path)],
                cwd=str(self.root_dir),
                capture_output=True,
                text=True,
                check=False
            )
            
            success = (result.returncode == 0)
            return ProcessResult(
                step_name="Portfolio History",
                success=success,
                output=result.stdout,
                error=result.stderr if not success else None
            )
        except Exception as e:
            return ProcessResult("Portfolio History", False, "", str(e))

    def run_full_import(self, uploaded_file) -> List[ProcessResult]:
        """
        Orchestrates the full import pipeline: Save -> Parse -> History.
        Returns a list of results for each step.
        """
        results = []
        
        # 1. Save
        try:
            saved_path = self.save_uploaded_file(uploaded_file, uploaded_file.name)
            results.append(ProcessResult("File Save", True, f"Saved to {saved_path}"))
        except Exception as e:
            results.append(ProcessResult("File Save", False, "", str(e)))
            return results
            
        # 2. Parse
        parse_res = self.run_parser() # Auto-discovery preferred or pass saved_path?
        # If we pass saved_path, we avoid ambiguity.
        # But run_csv_parser.py might expect just filename or relative path?
        # Let's rely on auto-discovery for now as it mirrors CLI usage.
        results.append(parse_res)
        
        if not parse_res.success:
            return results
            
        # 3. History
        hist_res = self.run_portfolio_history()
        results.append(hist_res)
        
        return results
