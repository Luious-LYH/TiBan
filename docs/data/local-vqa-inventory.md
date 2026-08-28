# Local VQA inventory

- Root: `E:\2.Projects\ARIS\VQA\data`
- Mode: read-only; source files were not moved, renamed or modified.

| Dataset | QA | image files | images referenced | linked rows | linkage | duplicate IDs | candidate usage | hash |
|---|---:|---:|---:|---:|---:|---|---|---|
| kvasir-vqa | 58849 | 6507 | 6500 | 58849 | 100.0% | 0 | `suitability_classified` | `6be1ee739519aee4` |
| kvasir-vqa-x1 | 159549 | 6500 | 6449 | 159549 | 100.0% | 0 | `generation_source` | `498be08485147232` |
| endobench | 6832 | 6832 | 6832 | 6832 | 100.0% | 0 | `benchmark_only` | `3c957b9213a76c28` |

## kvasir-vqa

- Local path: `E:\2.Projects\ARIS\VQA\data\Kvasir-VQA`
- Files: `6588`; image files: `6507`
- JSON: `E:\2.Projects\ARIS\VQA\data\Kvasir-VQA\Kvasir-VQA.json`
- Schema sample: `answer, dataset, gt, id, image_path, img_id, question, source`
- Question types: `{"visual_observation": 43606, "true_false": 15243}`
- Answer types: `{"structured_answer": 43606, "yes_no": 15243}`
- License/source: `CC BY-NC 4.0` · `https://github.com/ENDObenchmark/Kvasir-VQA`
- Candidate business usage: `suitability_classified`
- Missing assets sample: `[]`
- Policy: EndoBench is `benchmark_only`; Kvasir-VQA-x1 defaults to `generation_source`; Kvasir-VQA requires suitability classification.

## kvasir-vqa-x1

- Local path: `E:\2.Projects\ARIS\VQA\data\Kvasir-VQA-x1`
- Files: `13020`; image files: `6500`
- JSON: `E:\2.Projects\ARIS\VQA\data\Kvasir-VQA-x1\Kvasir-VQA-x1.json`
- Schema sample: `answer, complexity, dataset, gt, id, image_path, image_url, img_id, original, question, question_class, split`
- Question types: `{"multi_aspect_structured": 159549}`
- Answer types: `{"structured_answer": 159549}`
- License/source: `CC BY-NC 4.0` · `https://github.com/ENDObenchmark/Kvasir-VQA-x1`
- Candidate business usage: `generation_source`
- Missing assets sample: `[]`
- Policy: EndoBench is `benchmark_only`; Kvasir-VQA-x1 defaults to `generation_source`; Kvasir-VQA requires suitability classification.

## endobench

- Local path: `E:\2.Projects\ARIS\VQA\data\EndoBench`
- Files: `6837`; image files: `6832`
- JSON: `E:\2.Projects\ARIS\VQA\data\EndoBench\EndoBench.json`
- Schema sample: `answer, category, dataset, gt, id, image_path, options, original_image_path, question, scene, subtask, task`
- Question types: `{"visual_observation": 6832}`
- Answer types: `{"structured_answer": 6832}`
- License/source: `CC BY-SA 3.0` · `https://github.com/medAI-NEU/EndoBench`
- Candidate business usage: `benchmark_only`
- Missing assets sample: `[]`
- Policy: EndoBench is `benchmark_only`; Kvasir-VQA-x1 defaults to `generation_source`; Kvasir-VQA requires suitability classification.
