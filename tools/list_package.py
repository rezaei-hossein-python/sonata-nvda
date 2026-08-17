import zipfile
pkg='sonata_neural_voices-3.1.nvda-addon'
with zipfile.ZipFile(pkg,'r') as z:
    for e in sorted(z.namelist())[:200]:
        print(e)
