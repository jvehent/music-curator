import sys
import webbrowser
import threading
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.ui.server import start_server


def open_browser(port: int = 8765):
    time.sleep(1.2)
    webbrowser.open(f"http://localhost:{port}")


def main():
    port = 8765
    print("\n=======================================================")
    print("🎵 Starting Harmoniq Music Curator...")
    print(f"   Opening http://localhost:{port} in your browser")
    print("   Press Ctrl+C in this terminal to stop the application")
    print("=======================================================\n")
    
    # Auto-open browser
    t = threading.Thread(target=open_browser, args=(port,), daemon=True)
    t.start()

    # Launch server
    start_server(port=port)


if __name__ == "__main__":
    main()
