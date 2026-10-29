import pathlib,subprocess,sys
root=pathlib.Path(__file__).resolve().parent
for p in [*root.glob('*.py'),*root.glob('tests/*.py')]:compile(p.read_text(),str(p),'exec')
raise SystemExit(subprocess.call([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=root))
