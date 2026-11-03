"""
FaceLock Complete Test Suite Runner
Executes the comprehensive suite of unit, integration, and security tests.
"""
import sys
import subprocess


def run_all():
    print("=" * 65)
    print("  FACELOCK COMPREHENSIVE TEST SUITE")
    print("=" * 65)

    cmd = [sys.executable, "-m", "pytest", "tests/", "-v"]
    res = subprocess.run(cmd)
    
    print("\n" + "=" * 65)
    if res.returncode == 0:
        print("  ALL TESTS PASSED SUCCESSFULLY (100% OPERATIONAL)")
    else:
        print("  SOME TESTS FAILED - REVIEW LOGS ABOVE")
    print("=" * 65)
    sys.exit(res.returncode)


if __name__ == "__main__":
    run_all()
