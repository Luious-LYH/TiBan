import { execFileSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const backendRoot = path.resolve(frontendRoot, '..', 'backend')
const outputRoot = path.resolve(frontendRoot, 'backend-runtime')
const workRoot = path.resolve(frontendRoot, 'build-desktop-backend')
const entryPoint = path.join(backendRoot, 'desktop_server.py')
// Electron launches the child with windowsHide=true and stdio ignored. A
// console-subsystem backend is therefore invisible in the desktop app, while
// avoiding the runw bootloader's stdout-less startup behaviour on Windows.
const consoleMode = process.env.TIBAN_DESKTOP_NOCONSOLE === 'true' ? '--noconsole' : '--console'
const backendName = process.env.TIBAN_DESKTOP_BACKEND_NAME || 'tiban-backend'

const dataArg = (source, target) => `${source};${target}`

execFileSync('python', [
  '-m', 'PyInstaller',
  '--noconfirm',
  '--clean',
  '--onefile',
  consoleMode,
  '--name', backendName,
  '--distpath', outputRoot,
  '--workpath', workRoot,
  '--specpath', workRoot,
  '--paths', backendRoot,
  '--add-data', dataArg(path.join(backendRoot, 'app', 'data'), 'app/data'),
  '--add-data', dataArg(path.join(backendRoot, 'app', 'agents'), 'app/agents'),
  '--collect-submodules', 'app',
  // FastEmbed and sentence-transformers are optional source/developer
  // fallbacks. The desktop bundle uses the configured remote Embedding API.
  '--exclude-module', 'fastembed',
  '--exclude-module', 'sentence_transformers',
  '--exclude-module', 'torch',
  '--exclude-module', 'torchvision',
  '--exclude-module', 'IPython',
  '--exclude-module', 'jupyter',
  '--exclude-module', 'notebook',
  '--exclude-module', 'nbformat',
  '--exclude-module', 'nbconvert',
  '--exclude-module', 'matplotlib',
  '--exclude-module', 'pandas',
  '--exclude-module', 'scipy',
  '--exclude-module', 'skimage',
  '--exclude-module', 'sklearn',
  '--exclude-module', 'statsmodels',
  '--exclude-module', 'patsy',
  '--exclude-module', 'xarray',
  '--exclude-module', 'pyarrow',
  '--exclude-module', 'tables',
  '--exclude-module', 'numba',
  '--exclude-module', 'llvmlite',
  '--exclude-module', 'h5py',
  '--exclude-module', 'bokeh',
  '--exclude-module', 'plotly',
  '--exclude-module', 'panel',
  '--exclude-module', 'holoviews',
  '--exclude-module', 'pyviz_comms',
  '--exclude-module', 'PyQt5',
  '--exclude-module', 'qtpy',
  '--exclude-module', 'tkinter',
  '--exclude-module', 'sphinx',
  '--exclude-module', 'docutils',
  entryPoint,
], { cwd: frontendRoot, stdio: 'inherit' })

console.log('Built self-contained TiBan backend runtime.')
