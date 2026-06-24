from __future__ import annotations

import threading
import time
import webbrowser

from rincell.web import create_app


def open_browser(port: int) -> None:
    time.sleep(1.0)
    webbrowser.open(f"http://127.0.0.1:{port}/")


def main() -> None:
    port = 5000
    threading.Thread(target=open_browser, args=(port,), daemon=True).start()
    app = create_app()
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
