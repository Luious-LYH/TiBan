import { execFileSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const backendRoot = resolve(frontendRoot, '../backend')
const schemaPath = resolve(frontendRoot, '.generated/openapi.json')
const generator = resolve(frontendRoot, 'node_modules/openapi-typescript/bin/cli.js')
const outputPath = resolve(frontendRoot, 'src/api/generated.ts')

function resolvePython() {
  if (process.env.TIBAN_PYTHON && existsSync(process.env.TIBAN_PYTHON)) {
    return process.env.TIBAN_PYTHON
  }

  if (process.platform !== 'win32') {
    return 'python3'
  }

  // Windows may put the Microsoft Store shim before the real interpreter.
  // Resolve every PATH candidate and skip that non-executable placeholder.
  try {
    const candidates = execFileSync('where.exe', ['python'], { encoding: 'utf8' })
      .split(/\r?\n/)
      .map((candidate) => candidate.trim())
      .filter(Boolean)
    const realPython = candidates.find(
      (candidate) => existsSync(candidate) && !candidate.toLowerCase().includes('windowsapps'),
    )
    if (realPython) return realPython
  } catch {
    // Fall through to the regular command name for environments where `where`
    // is unavailable or Python is provided by a shell alias.
  }
  return 'python'
}

execFileSync(resolvePython(), ['scripts/export_openapi.py', schemaPath], {
  cwd: backendRoot,
  stdio: 'inherit',
})
execFileSync(process.execPath, [generator, schemaPath, '--output', outputPath], { cwd: frontendRoot, stdio: 'inherit' })
