"""
FaceLock Cross-Platform Standalone Executable Builder
Builds standalone binary distribution for Windows or Linux using PyInstaller.
"""
import os
import sys
import shutil
import subprocess

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def build():
    os.chdir(PROJECT_ROOT)
    print("=" * 65)
    print(f"  Building FaceLock Standalone Executable for {sys.platform.upper()}")
    print("=" * 65)

    spec_file = os.path.join(PROJECT_ROOT, "facelock.spec")
    if not os.path.exists(spec_file):
        print(f"[ERROR] Specification file not found: {spec_file}")
        sys.exit(1)

    # Clean previous build artifacts
    for d in ("build", "dist"):
        p = os.path.join(PROJECT_ROOT, d)
        if os.path.exists(p):
            print(f"Cleaning {p} ...")
            shutil.rmtree(p)

    cmd = [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", spec_file]
    print(f"Running: {' '.join(cmd)}")
    res = subprocess.run(cmd)

    if res.returncode != 0:
        print("[FAILED] PyInstaller build failed.")
        sys.exit(res.returncode)

    dist_dir = os.path.join(PROJECT_ROOT, "dist", "FaceLock")
    if os.path.exists(dist_dir):
        print("\n" + "=" * 65)
        print("  BUILD SUCCESSFUL!")
        print(f"  Output folder: {dist_dir}")
        if sys.platform == "win32":
            exe_path = os.path.join(dist_dir, "FaceLock.exe")
            print(f"  Executable: {exe_path}")
        else:
            bin_path = os.path.join(dist_dir, "FaceLock")
            print(f"  Executable: {bin_path}")
        print("=" * 65)
    else:
        print("[WARNING] Build completed but output folder not found.")


if __name__ == "__main__":
    build()
