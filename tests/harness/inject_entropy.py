#!/usr/bin/env python3
"""
Simple entropy injection script for skill breaking.
Fixes Windows/bash compatibility issues with sed.
"""
import sys
import re
from pathlib import Path

def inject_missing_step(skill_md):
    """Comment out numbered steps"""
    with open(skill_md, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find Steps section and comment out numbered lines
    lines = content.split('\n')
    in_steps = False
    modified = False
    
    print(f"[DEBUG] Total lines: {len(lines)}")
    
    for i, line in enumerate(lines):
        if line.startswith('## Steps'):
            in_steps = True
            print(f"[DEBUG] Found ## Steps at line {i}")
            continue
        if in_steps and line.startswith('##'):
            in_steps = False
            print(f"[DEBUG] Left Steps section at line {i}")
        
        if in_steps:
            print(f"[DEBUG] In steps, line {i}: {repr(line[:40])}")
            if re.match(r'^\d+\.', line):
                print(f"[DEBUG] Matched numbered step: {repr(line[:40])}")
                lines[i] = '# BROKEN: ' + line
                modified = True
    
    print(f"[DEBUG] Modified: {modified}")
    
    if modified:
        with open(skill_md, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        print("[OK] Injected missing-step failure")
        return True
    else:
        print("[ERROR] No steps found to inject")
        return False

def inject_corrupted_logic(skill_md):
    """Corrupt the logic"""
    with open(skill_md, 'r', encoding='utf-8') as f:
        content = f.read()
    
    modified_content = content.replace(
        'must follow the spec exactly',
        'can deviate from spec as needed'
    )
    
    if modified_content != content:
        with open(skill_md, 'w', encoding='utf-8') as f:
            f.write(modified_content)
        print("[OK] Injected corrupted-logic failure")
        return True
    else:
        print("[ERROR] Could not find logic pattern")
        return False

def inject_incomplete_doc(skill_md):
    """Remove output documentation"""
    with open(skill_md, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Find and remove Output section
    output_start = None
    output_end = None
    
    for i, line in enumerate(lines):
        if line.startswith('## Output'):
            output_start = i
        elif output_start is not None and line.startswith('##'):
            output_end = i
            break
    
    if output_start is not None:
        output_end = output_end or len(lines)
        del lines[output_start:output_end]
        
        with open(skill_md, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print("[OK] Injected incomplete-doc failure")
        return True
    else:
        print("[ERROR] Could not find Output section")
        return False

if __name__ == '__main__':
    print(f"[DEBUG] Script started with argv: {sys.argv}")
    
    if len(sys.argv) < 3:
        print("Usage: inject_entropy.py <skill_md> <failure_type>")
        sys.exit(1)
    
    skill_md = sys.argv[1]
    failure_type = sys.argv[2]
    
    print(f"[DEBUG] Arguments: skill_md={skill_md}, failure_type={failure_type}")
    
    if not Path(skill_md).exists():
        print(f"[ERROR] File not found: {skill_md}")
        sys.exit(1)
    
    print(f"[DEBUG] File exists, size: {Path(skill_md).stat().st_size} bytes")
    
    if failure_type == 'missing-step':
        print(f"[DEBUG] Running inject_missing_step()")
        success = inject_missing_step(skill_md)
    elif failure_type == 'corrupted-logic':
        print(f"[DEBUG] Running inject_corrupted_logic()")
        success = inject_corrupted_logic(skill_md)
    elif failure_type == 'incomplete-doc':
        print(f"[DEBUG] Running inject_incomplete_doc()")
        success = inject_incomplete_doc(skill_md)
    else:
        print(f"[ERROR] Unknown failure type: {failure_type}")
        sys.exit(1)
    
    print(f"[DEBUG] Function returned: success={success}")
    sys.exit(0 if success else 1)

