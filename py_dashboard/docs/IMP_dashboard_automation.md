# Role: Senior Software Architect

## Context
We need to enhance the existing Streamlit Dashboard to allow users to upload broker CSV files directly. This upload should trigger a backend processing pipeline:
1.  Save CSV to project root.
2.  Execute `run_csv_parser.py` (imports to `trades.xml` and moves CSV to `oldcsv`).
3.  Execute `run_portfolio_history.py` (updates `journal.csv`).
4.  Refresh Dashboard data.

## PART 1: The System Skeleton (Shared Context)

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List
import subprocess

@dataclass
class ProcessResult:
    success: bool
    output: str
    error: Optional[str] = None

class WorkflowManager:
    """
    Manages the file upload and external script execution workflow.
    Designed to be used within the Streamlit app but decoupled from UI logic.
    """
    
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        
    def save_uploaded_file(self, file_obj, filename: str) -> Path:
        """
        Saves the uploaded file object (from Streamlit) to the project root.
        Returns the absolute path to the saved file.
        """
        # TODO: Implement safe saving logic
        pass

    def run_parser(self, csv_path: Path) -> ProcessResult:
        """
        Triggers 'run_csv_parser.py' with the given csv_path.
        Captures stdout/stderr.
        """
        # TODO: Implement subprocess call
        pass

    def run_portfolio_history(self) -> ProcessResult:
        """
        Triggers 'run_portfolio_history.py'.
        Captures stdout/stderr.
        """
        # TODO: Implement subprocess call
        pass

    def run_full_import(self, file_obj, filename: str) -> List[ProcessResult]:
        """
        Orchestrates the full import pipeline: Save -> Parse -> History.
        Returns a list of results for each step.
        """
        # TODO: Orchestrate steps
        pass
```

## PART 2: Implementation Work Orders

### Task ID: [T-DASHAUTO-010]
**Target File**: `py_dashboard/workflow_manager.py`
**Description**: Implement the `WorkflowManager` class.
**Context**: Use the Skeleton above. Implement saving logic using standard file write. Use `subprocess.run` for script execution, ensuring current working directory is set correctly to `self.root_dir`.
**Algo/Logic Steps**:
1.  **save_uploaded_file**: Open `self.root_dir / filename` in 'wb' mode and write `file_obj.getbuffer()`. Return path.
2.  **run_parser**: Run `python run_csv_parser.py [csv_path]` using `sys.executable`. Check `returncode`. If 0, success.
3.  **run_portfolio_history**: Run `python run_portfolio_history.py`.
4.  **run_full_import**: Call 1, 2, 3 in sequence. If any step fails, stop and return the results collected so far.

### Task ID: [T-DASHAUTO-020]
**Target File**: `py_dashboard/run_dashboard.py` (and potentially `py_dashboard/sidebar.py` if refactored, but likely main file)
**Description**: Integrate the Uploader UI.
**Context**: Use `st.file_uploader`.
**Algo/Logic Steps**:
1.  Add `st.sidebar.markdown("### Import")`.
2.  Add `uploaded_file = st.sidebar.file_uploader(...)`.
3.  Add a "Process" button `if st.sidebar.button("Run Import")`.
4.  Instantiate `WorkflowManager(Path(".."))` (relative to dashboard, or absolute).
5.  Call `run_full_import`.
6.  Display results (Success/Error logs) in `st.sidebar` or `st.expander`.
7.  If success, `st.cache_data.clear()` and `st.rerun()`.

