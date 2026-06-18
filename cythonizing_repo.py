#!/usr/bin/env python3
"""cythonizing_repo.py

Cythonization script to convert Python files to Cython compiled modules.

IMPORTANT:
- Never rename/delete ``__init__.py`` files. Removing them breaks regular packages and
  turns them into namespace packages, which causes import errors like:
  ``ImportError: cannot import name 'create_app' from 'app' (unknown location)``.
- Prefer copying ``.py`` -> ``.pyx`` instead of renaming so the original Python
  source remains as a safe fallback at runtime.
"""

import os
import shutil
import subprocess
from pathlib import Path


def _has_compiled_neighbor(py_file: Path) -> bool:
    """Return True if `py_file` appears to have a compiled extension next to it.

    We consider both Linux `.so` and Windows `.pyd` artifacts, and we accept any
    CPython ABI suffixes (e.g., `module.cpython-312-x86_64-linux-gnu.so`).
    """
    stem = py_file.with_suffix("").name
    parent = py_file.parent
    # Any compiled artifact starting with "{stem}." and ending in .so/.pyd
    for ext in (".so", ".pyd"):
        if any(parent.glob(f"{stem}.*{ext}")):
            return True
    return False


def cythonize_project():
    """Find, rename, and Cythonize all Python files except entry points."""
    
    # Define files to skip.
    # - Entry points: keep as .py
    # - Package initializers are skipped elsewhere (by filename)
    # - Some modules rely on dynamic typing constructs (e.g., Literal[*OPTIONS]) that
    #   don't survive Cython compilation reliably and can crash at import time.
    skip_files = {
        'src/run.py',
        # Langmanus graph typing-heavy modules (dynamic Literals)
        'src/app/utills/langmanus_graph_utills/graph/types.py',
        'src/app/utills/langmanus_graph_utills/graph/nodes.py',
    }
    
    # Step 1: Find all .py files and convert to .pyx (except skipped ones)
    print("Step 1: Converting .py files to .pyx...")
    py_files = []
    for dp, dn, fs in os.walk('.'):
        for f in fs:
            if f.endswith('.py'):
                file_path = Path(dp) / f
                rel_path = str(file_path)

                # Never touch package initializers; required for normal package imports
                if f == "__init__.py":
                    print(f"  Skipping package initializer: {rel_path}")
                    continue
                
                # Check if this file should be skipped
                normalized = str(file_path).lstrip('./')
                if rel_path in skip_files or normalized in skip_files:
                    print(f"  Skipping: {rel_path}")
                    continue
                
                py_files.append(rel_path)
    
    # Copy .py to .pyx (do NOT rename, keep .py as fallback)
    for py_file in py_files:
        pyx_file = py_file[:-3] + '.pyx'
        try:
            shutil.copy2(py_file, pyx_file)
            print(f"  Copied: {py_file} → {pyx_file}")
        except Exception as e:
            print(f"  Error converting {py_file}: {e}")
    
    # Step 2: Cythonize all .pyx files
    print("\nStep 2: Cythonizing .pyx files...")
    pyx_files = list(Path('.').rglob('*.pyx'))
    
    if not pyx_files:
        print("  No .pyx files found!")
        return
    
    for pyx_file in pyx_files:
        if pyx_file.is_file():
            try:
                print(f"  Cythonizing: {pyx_file}")
                result = subprocess.run(
                    [
                        'cythonize',
                        # Build extension module in-place
                        '-i',
                        # Do NOT treat Python annotations (e.g., `arg: str`) as Cython types.
                        # This prevents runtime type-enforcement issues after compilation when code
                        # intentionally passes callables/duck-typed values.
                        '-X', 'annotation_typing=False',
                        str(pyx_file),
                    ],
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    print(f"    Warning: {result.stderr}")
                else:
                    print(f"    ✓ Success")
            except Exception as e:
                print(f"  Error cythonizing {pyx_file}: {e}")
    
    # Step 3: Clean up temporary files
    print("\nStep 3: Cleaning up temporary files...")
    # We only want to remove generated artifacts (.pyx and generated C files)
    files_to_delete = list(Path('.').rglob('*.pyx')) + list(Path('.').rglob('*.c'))
    
    for file_path in files_to_delete:
        try:
            file_path.unlink()
            print(f"  Deleted: {file_path}")
        except Exception as e:
            print(f"  Error deleting {file_path}: {e}")

    # Optional Step 4: Remove python sources under src/app when compiled modules exist.
    # This is useful for code protection/obfuscation, but MUST be done carefully.
    if str(os.getenv("DELETE_APP_PY", "")).strip().lower() in ("1", "true", "yes", "y", "on"):
        print("\nStep 4: Deleting src/app/*.py sources where a compiled module exists...")
        app_root = Path("src") / "app"
        if app_root.exists():
            removed = 0
            skipped = 0
            for py in app_root.rglob("*.py"):
                # Never delete package initializers
                if py.name == "__init__.py":
                    skipped += 1
                    continue
                # Never delete explicitly skipped (uncompiled) files
                rel = py.as_posix()
                if rel in skip_files:
                    skipped += 1
                    continue
                # Only delete if compiled artifact exists right next to it
                if _has_compiled_neighbor(py):
                    try:
                        py.unlink()
                        removed += 1
                    except Exception as e:
                        print(f"  Error deleting {py}: {e}")
                else:
                    skipped += 1
            print(f"  Deleted {removed} .py files under src/app (skipped {skipped}).")
        else:
            print("  src/app not found; nothing to delete.")
    
    print("\n✓ Cythonization process completed successfully!")


if __name__ == '__main__':
    cythonize_project()
