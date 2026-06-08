import sys
import os

# Add backend/ to path for app.* imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
# Add project root to path for simulator.* imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
