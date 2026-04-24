import sys

with open('.github/workflows/ci-standard.yml', 'r') as f:
    content = f.read()

# Replace . .ci-venv/bin/activate with OS-agnostic alternative
# or use cross-platform activation logic. Or just avoid it.
# Actually github actions provides an easy way to just run inside the venv:
# .ci-venv/bin/python -m pip install
# or for powershell on windows it's .ci-venv\Scripts\Activate.ps1
