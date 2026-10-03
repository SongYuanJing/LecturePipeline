"""First-run device report using the selected release and private runtime."""
import argparse
import json
import sys
from launch import ROOT, app_root


def report(root=ROOT, mode='auto'):
    app = app_root(root)
    if str(app) not in sys.path:
        sys.path.insert(0, str(app))
    from asr_device import detect
    return detect(root, root / 'runtime/asr/python.exe', root / 'models/huggingface/hub',
                  root / 'runtime/cuda/v1.3', mode, inventory=True)


def selection(root, mode):
    value = report(root, mode)
    from asr_device import select
    return select(mode, value)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('auto', 'cpu', 'gpu'), default='auto', nargs='?')
    args = parser.parse_args()
    print(json.dumps(report(ROOT, args.mode), ensure_ascii=False))
