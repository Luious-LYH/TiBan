import { execFileSync } from 'node:child_process'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const backendRoot = resolve(frontendRoot, '../backend')
const schemaPath = resolve(frontendRoot, '.generated/openapi.json')
const generator = resolve(frontendRoot, 'node_modules/openapi-typescript/bin/cli.js')
const outputPath = resolve(frontendRoot, 'src/api/generated.ts')

execFileSync('python', ['scripts/export_openapi.py', schemaPath], {
  cwd: backendRoot,
  stdio: 'inherit',
})
execFileSync(process.execPath, [generator, schemaPath, '--output', outputPath], { cwd: frontendRoot, stdio: 'inherit' })
