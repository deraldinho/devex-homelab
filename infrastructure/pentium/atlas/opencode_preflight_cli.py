"""Read-only preflight command. Never loads credentials."""
import argparse
import json
from .opencode_host_preflight import inspect_opencode_host

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--binary",required=True)
    args=parser.parse_args()
    outcome=inspect_opencode_host(args.binary)
    print(json.dumps({"state":outcome.state,"reason":outcome.reason,
                      "version":outcome.version}))
    return 0 if outcome.state=="READY" else 2
if __name__=="__main__":
    raise SystemExit(main())
