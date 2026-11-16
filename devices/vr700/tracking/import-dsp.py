#!/usr/bin/env python3
"""Import the pinned VR700 DSP and sensor metadata runtime offline."""
import argparse
import json
import os
from pathlib import Path
from runtime_import import validate_runtime, write_runtime


def main():
    os.umask(0o022)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True,
                        help='New qcom runtime root containing dsp, sensors and socinfo')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output must be new')
    try:
        lock, checked = validate_runtime(args.stock, args.manifest)
        receipt = write_runtime(args.output, lock, checked)
    except (KeyError, ValueError, OSError) as error:
        parser.error(str(error))
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
