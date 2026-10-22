"""Settings from environment variables, with backend/.env for local development.

Secrets stay out of the code and out of git: .env is git-ignored, and
.env.example lists the variables with placeholder values.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# override=False: a variable already set in the real environment wins.
load_dotenv(Path(__file__).parents[2] / ".env", override=False)

# The model that reads label photos; the eval compares models.
LABEL_MODEL = os.environ.get("LABEL_MODEL", "claude-opus-5-5")
