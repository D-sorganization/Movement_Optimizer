import glob
import os
import re

workflows_dir = r"c:\Users\diete\Repositories\Movement-Optimizer\.github\workflows"
for yaml_file in glob.glob(os.path.join(workflows_dir, "*.yml")):
    with open(yaml_file, encoding="utf-8") as f:
        content = f.read()

    # We want to replace unpatched version
    unpatched = r'([ \t]*)echo "runner=d-sorg-fleet" >> \$GITHUB_OUTPUT'
    unpatched2 = r'([ \t]*)echo "runner=d-sorg-fleet" >> "\$GITHUB_OUTPUT"'

    changed = False

    if 'mkdir -p "$(dirname "$GITHUB_OUTPUT")"' not in content:
        if re.search(unpatched, content):
            content = re.sub(
                unpatched,
                r'\1mkdir -p "$(dirname "$GITHUB_OUTPUT")" && echo "runner=d-sorg-fleet" >> "$GITHUB_OUTPUT"',
                content,
            )
            changed = True
        if re.search(unpatched2, content):
            content = re.sub(
                unpatched2,
                r'\1mkdir -p "$(dirname "$GITHUB_OUTPUT")" && echo "runner=d-sorg-fleet" >> "$GITHUB_OUTPUT"',
                content,
            )
            changed = True

    if changed:
        with open(yaml_file, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Patched {yaml_file}")
