import runpy
import glob
import traceback
import sys

failed = []
for tf in sorted(glob.glob('tests/test_*.py')):
    print(f'RUN {tf}')
    try:
        runpy.run_path(tf, run_name='__main__')
    except Exception:
        print('FAILED:')
        traceback.print_exc()
        failed.append(tf)
    else:
        print('PASS')

print('\nSUMMARY:')
print(f'Ran {len(sorted(glob.glob("tests/test_*.py")))} tests files; Failures: {len(failed)}')
if failed:
    print('\nFailed files:')
    for f in failed:
        print(f)
    sys.exit(1)
