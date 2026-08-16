import sys
import polib

args = sys.argv[1:]
mo_file = None
po_file = None

i = 0
while i < len(args):
    arg = args[i]
    if arg == '-o' and i + 1 < len(args):
        mo_file = args[i+1]
        i += 2
    elif arg.endswith('.po'):
        po_file = arg
        i += 1
    else:
        i += 1

if mo_file and po_file:
    po = polib.pofile(po_file)
    po.save_as_mofile(mo_file)
    print(f"Compiled {po_file} -> {mo_file}")
else:
    print("Invalid msgfmt arguments:", args)
    sys.exit(1)
