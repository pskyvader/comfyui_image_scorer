import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from comfyui_image_scorer.adapters.cli.main import main
sys.exit(main())
