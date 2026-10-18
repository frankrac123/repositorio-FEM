from pathlib import Path
import os
import sys
import traceback

os.chdir(Path(__file__).resolve().parent)
try:
    from trusslab.ui import main
    raise SystemExit(main())
except Exception:
    Path('data').mkdir(exist_ok=True)
    Path('data/startup_error.log').write_text(traceback.format_exc(),encoding='utf-8')
    raise
