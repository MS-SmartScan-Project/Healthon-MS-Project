"""Run one image through the local detector without changing the source image."""
import json
import os
import shutil
import sys
import tempfile

import detector


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python predict.py <image>", file=sys.stderr)
        return 2

    source = os.path.abspath(sys.argv[1])
    if not os.path.isfile(source):
        print(json.dumps({"error": "image not found"}))
        return 2
    if not detector.load_model():
        print(json.dumps({"error": detector.status()["error"]}))
        return 1

    try:
        with tempfile.TemporaryDirectory() as directory:
            working = os.path.join(directory, "input.png")
            enhanced = os.path.join(directory, "enhanced.png")
            annotated = os.path.join(directory, "annotated.png")
            shutil.copyfile(source, working)
            result = detector.analyze(working, enhanced, annotated)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
