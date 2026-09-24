"""Future D1 entry point; fail-closed until a separate authorization artifact exists."""
import argparse, json
from pathlib import Path
try:
    from .d1_harness import load_manifest, verify_sources, build_all
except ImportError:
    from d1_harness import load_manifest, verify_sources, build_all

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--execute",action="store_true"); ap.add_argument("--dry-run",action="store_true"); args=ap.parse_args()
    m=load_manifest(); verify_sources(m)
    if args.execute and not m.get("execution_authorized",False):
        raise SystemExit("D1 execution is unauthorized; no provider request was sent")
    if args.execute:
        raise SystemExit("D1 execution runner is not enabled in the preparation commit")
    print(json.dumps({"records":len(build_all(m)["records"]),"provider_requests_sent":0,"execution_authorized":False}))
if __name__=="__main__": main()
