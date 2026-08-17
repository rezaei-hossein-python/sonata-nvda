import zipfile, shutil, os
pkg='sonata_neural_voices-3.1.nvda-addon'
tmp='sonata_neural_voices-3.1.clean.nvda-addon'
with zipfile.ZipFile(pkg,'r') as zin:
    with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED) as zout:
        for zinfo in zin.infolist():
            name = zinfo.filename
            if '__pycache__' in name or name.endswith('.pyc') or name.endswith('.pcm'):
                print('Excluding', name)
                continue
            data = zin.read(name)
            zout.writestr(zinfo, data)
shutil.move(tmp, pkg)
print('Repacked', pkg)
