import os
import re

def get_description(frontmatter):
    block_match = re.search(r'^description:\s*([>|])\s*\n((?:[ \t]+.*\n?)*)', frontmatter, re.MULTILINE)
    if block_match:
        content = block_match.group(2)
        lines = [line.strip() for line in content.splitlines()]
        return " ".join(lines).strip()

    line_match = re.search(r'^description:\s*(.*)', frontmatter, re.MULTILINE)
    if line_match:
        desc = line_match.group(1).strip()
        if (desc.startswith('"') and desc.endswith('"')) or (desc.startswith("'") and desc.endswith("'")):
            desc = desc[1:-1]
        return desc

    return None

def check_skills():
    skills_dir = 'skills'
    desc_threshold = 1024

    skills = []

    for root, _, files in os.walk(skills_dir):
        if 'SKILL.md' in files:
            file_path = os.path.join(root, 'SKILL.md')
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
                continue

            file_size = os.path.getsize(file_path)
            description = None
            fm_match = re.search(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL | re.MULTILINE)
            if fm_match:
                description = get_description(fm_match.group(1))

            skills.append({
                'path': file_path,
                'file_size': file_size,
                'desc_len': len(description) if description else 0,
            })

    if not skills:
        print("No SKILL.md files found.")
        return

    print("=== Top 5 Largest Descriptions ===")
    for s in sorted(skills, key=lambda s: s['desc_len'], reverse=True)[:5]:
        print(f"  {s['path']}: {s['desc_len']} chars")

    print()

    overlong = [s for s in skills if s['desc_len'] > desc_threshold]
    if overlong:
        print(f"=== Descriptions > {desc_threshold} chars ===")
        for s in sorted(overlong, key=lambda s: s['desc_len'], reverse=True):
            print(f"  {s['path']}: {s['desc_len']} chars")
        print()

    print("=== SKILL.md File Sizes ===")
    for s in sorted(skills, key=lambda s: s['file_size'], reverse=True):
        print(f"  {s['path']}: {s['file_size']:,} bytes")

if __name__ == "__main__":
    check_skills()
