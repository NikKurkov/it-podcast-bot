import argparse
import socket
import sys
import time


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Wait until a TCP endpoint accepts connections.")
    parser.add_argument("host")
    parser.add_argument("port", type=int)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--interval", type=float, default=1.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    deadline = time.monotonic() + args.timeout
    last_error = ""

    while time.monotonic() < deadline:
        try:
            with socket.create_connection((args.host, args.port), timeout=min(args.interval, 3.0)):
                print(f"TCP endpoint is ready: {args.host}:{args.port}")
                return
        except OSError as exc:
            last_error = str(exc)
            time.sleep(args.interval)

    print(
        f"TCP endpoint did not become ready within {args.timeout:.0f}s: "
        f"{args.host}:{args.port}. Last error: {last_error}",
        file=sys.stderr,
    )
    raise SystemExit(1)


if __name__ == "__main__":
    main()
