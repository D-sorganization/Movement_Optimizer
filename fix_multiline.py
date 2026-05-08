import glob
import os
import re

workflows_dir = r"c:\Users\diete\Repositories\Movement-Optimizer\.github\workflows"
for yaml_file in glob.glob(os.path.join(workflows_dir, "*.yml")):
    with open(yaml_file, encoding="utf-8") as f:
        content = f.read()

    # Replace multiline with single line
    content = re.sub(
        r'mkdir -p "\$\(dirname "\$GITHUB_OUTPUT"\)"\n\s*mkdir -p "\$\(dirname "\$GITHUB_OUTPUT"\)"\n\s*echo "runner=d-sorg-fleet" >> "\$GITHUB_OUTPUT"',
        r'mkdir -p "$(dirname "$GITHUB_OUTPUT")" && echo "runner=d-sorg-fleet" >> "$GITHUB_OUTPUT"',
        content,
    )
    # Also handle the single mkdir variant
    content = re.sub(
        r'mkdir -p "\$\(dirname "\$GITHUB_OUTPUT"\)"\n\s*echo "runner=d-sorg-fleet" >> "\?\$GITHUB_OUTPUT"\?',
        r'mkdir -p "$(dirname "$GITHUB_OUTPUT")" && echo "runner=d-sorg-fleet" >> "$GITHUB_OUTPUT"',
        content,
    )

    with open(yaml_file, "w", encoding="utf-8") as f:
        f.write(content)
