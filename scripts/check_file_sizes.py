"""Reject staged Git blobs larger than 1 MB (1,000,000 bytes)."""

import subprocess
import sys

MAX_BYTES = 1_000_000


def main():
    failed = False
    for filename in sys.argv[1:]:
        result = subprocess.run(
            ["git", "cat-file", "-s", ":" + filename],
            capture_output=True,
            text=True,
        )
        if result.returncode:
            print(f"Cannot inspect staged file: {filename}", file=sys.stderr)
            failed = True
            continue
        size = int(result.stdout)
        if size > MAX_BYTES:
            print(f"{filename}: {size:,} bytes exceeds limit of {MAX_BYTES:,} bytes")
            failed = True
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
