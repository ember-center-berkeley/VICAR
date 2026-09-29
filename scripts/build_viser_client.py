"""Build pinned Viser with the small, auditable augmentation playback extension.

Requires Node 24+ and npm on PATH. The installed viser==1.1.1 wheel includes
the original sources and lockfile; this script works on a temporary copy.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import viser

ROOT = Path(__file__).resolve().parents[1]


def patch(client):
    shutil.copyfile(ROOT / 'viser-client-extension/AugmentationPlayback.ts', client / 'src/AugmentationPlayback.ts')
    target = client / 'src/FilePlayback.tsx'
    text = target.read_text()
    replacements = [
        ('import { Message } from "./WebsocketMessages";',
         'import { Message } from "./WebsocketMessages";\nimport { AugmentationPlayback, attachAugmentation } from "./AugmentationPlayback";'),
        ('  const viewerMutable = viewer.mutable.current; // Get mutable once',
         '  const viewerMutable = viewer.mutable.current; // Get mutable once\n  const augmentation = useRef<AugmentationPlayback | null>(null);'),
        ('    if (batch.length > 0) enqueueMessages(viewerMutable, batch);',
         '    augmentation.current?.apply(mutable.currentTime, batch);\n    if (batch.length > 0) enqueueMessages(viewerMutable, batch);'),
        ('  }, [recording]);\n\n  useEffect(() => {',
         '  }, [recording]);\n\n  useEffect(() => {\n    if (recording === null) return;\n    return attachAugmentation(value => { augmentation.current = value; updatePlayback(); }, updatePlayback);\n  }, [recording, updatePlayback]);\n\n  useEffect(() => {'),
        ('            onClick={() => setPaused(!paused)}',
         '            aria-label={paused ? "Play motion" : "Pause motion"}\n            onClick={() => setPaused(!paused)}'),
        ('            value={currentTime.toFixed(1)}',
         '            aria-label="Playback time"\n            value={currentTime.toFixed(1)}'),
    ]
    for old, new in replacements:
        if text.count(old) != 1:
            raise ValueError(f'Viser source drift: expected exactly one patch anchor: {old[:60]}')
        text = text.replace(old, new)
    target.write_text(text)


def main():
    if viser.__version__ != '1.1.1':
        raise ValueError('This extension is tested against viser==1.1.1.')
    with tempfile.TemporaryDirectory(prefix='vicar-viser-') as temp:
        source = Path(viser.__file__).parent
        client = Path(temp) / 'client'
        shutil.copytree(source / 'client', client, ignore=shutil.ignore_patterns('node_modules', 'build'))
        shutil.copytree(source / '_assets', Path(temp) / '_assets')
        patch(client)
        subprocess.run(['npm', 'ci', '--no-audit', '--no-fund'], cwd=client, check=True)
        subprocess.run(['npm', 'run', 'typecheck'], cwd=client, check=True)
        subprocess.run(['npm', 'exec', '--', 'vite', 'build', '--base', './'], cwd=client, check=True)
        html = (client / 'build/index.html').read_text()
        (ROOT / 'viser-client/index.html').write_text('\n'.join(line.rstrip() for line in html.splitlines()) + '\n')


if __name__ == '__main__':
    main()
