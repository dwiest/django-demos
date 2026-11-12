"""Build a Python 3.12 x86_64 Lambda ZIP without changing Django dependencies."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / 'dist' / 'inventory-mcp-lambda.zip'


def main():
    OUTPUT.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='inventory-mcp-') as temp:
        stage = Path(temp)
        subprocess.run([
            sys.executable, '-m', 'pip', 'install', '--only-binary=:all:',
            '--platform', 'manylinux2014_x86_64', '--implementation', 'cp',
            '--python-version', '3.12', '--abi', 'cp312',
            '--target', str(stage), '-r', str(ROOT / 'requirements.txt'),
        ], check=True)
        for name in ('lambda_function.py', 'cognito_auth.py'):
            shutil.copy2(ROOT / name, stage / name)
        with zipfile.ZipFile(OUTPUT, 'w', zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(stage.rglob('*')):
                if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
                    archive.write(path, path.relative_to(stage))
    print(OUTPUT)


if __name__ == '__main__':
    main()

