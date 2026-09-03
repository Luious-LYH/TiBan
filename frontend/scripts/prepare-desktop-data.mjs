import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const sourceRoot = path.resolve(scriptDir, '../../data/external/CMExam')
const targetRoot = path.resolve(scriptDir, '../desktop-data/external/CMExam')
const sourceCsv = path.join(sourceRoot, 'data', 'test_with_annotations.csv')

if (!fs.existsSync(sourceCsv)) {
  throw new Error(`缺少本机 CMExam 数据：${sourceCsv}\n请先将已获授权的 CMExam 数据放入 data/external/CMExam。`)
}

fs.mkdirSync(path.dirname(path.join(targetRoot, 'data', 'test_with_annotations.csv')), { recursive: true })
fs.copyFileSync(sourceCsv, path.join(targetRoot, 'data', 'test_with_annotations.csv'))
for (const fileName of ['LICENSE', 'README.md']) {
  const source = path.join(sourceRoot, fileName)
  if (fs.existsSync(source)) fs.copyFileSync(source, path.join(targetRoot, fileName))
}

console.log('Prepared release-only CMExam desktop data bundle.')
