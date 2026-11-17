"""Owned loopback control relays, fixed destinations only. No arbitrary proxy."""
from http.server import ThreadingHTTPServer
import runpy
import threading

Handler = runpy.run_path("/proxy101.py")["Handler"]
for port, target in {14318: ("collector", 4318), 18888: ("collector", 8888),
                     19090: ("prometheus", 9090), 13000: ("grafana", 3000),
                     14321: ("traces", 4318), 14322: ("logs", 4318),
                     14323: ("metrics", 4318),
                     14324: ("dev-app", 8989), 14325: ("prod-app", 8989)}.items():
    server = ThreadingHTTPServer(("0.0.0.0", port), type("FixedRelay", (Handler,), {"upstream": target}))
    threading.Thread(target=server.serve_forever, daemon=True).start()
threading.Event().wait()
