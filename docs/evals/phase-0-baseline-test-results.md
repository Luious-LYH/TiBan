> Phase 0 当前版本验证结果。执行日期：2026-08-27。所有命令均为只读/构建/测试命令，未修改业务逻辑或安装依赖。

### Environment and scope

| Area | Working directory | Scope |
|---|---|---|
| Backend | `code/backend` | compile check + existing pytest suite |
| Frontend | `code/frontend` | existing build + existing lint script |
| Frontend test inventory | `code/frontend` | `package.json` has no `test` script；未发现 Vitest/RTL/Playwright test files |

### Backend

#### Compile

Command:

```powershell
python -m compileall -q app
```

Result:

```text
PASS
```

#### Existing test suite

Command:

```powershell
$env:PYTHONPATH = '.'
pytest -q
```

Result:

```text
18 passed, 1 warning in 1.63s
```

Warning：当前环境中的 FastAPI/Starlette TestClient 使用 `httpx` 的 deprecated import path，建议后续依赖升级时单独处理；Phase 0 不改依赖。

### Frontend

#### Production build

Command:

```powershell
npm run build
```

Result：

```text
PASS
vite v8.0.16
1760 modules transformed
✓ built in 783ms
build_exit=0
```

#### Lint

Command:

```powershell
npm run lint
```

Result：

```text
FAIL
69 problems (68 errors, 1 warning)
lint_exit=1
```

主要类别：

- `@typescript-eslint/no-explicit-any` 大量存在；
- React hook declaration/order 与变量先声明问题；
- `setState` in effect；
- 个别 hook dependency warning；
- 新旧页面、adapter 和手写类型并存导致的维护复杂度。

这些是已记录的 baseline，不在 Phase 0 通过局部修补解决；将在 Contract First 与 Frontend Product Rebuild 中以统一类型和页面重写方式处理。

### Frontend test gap

当前 `frontend/package.json` 只有 `dev`、`build`、Electron、`lint`、`preview` scripts，没有 `test` script。当前 frontend source tree 也没有 Vitest、React Testing Library 或 Playwright 测试文件。因此 Phase 0 只能确认 build/lint 基线，不能声称前端单测或 E2E 已通过。

### Acceptance decision

Phase 0 的验证结果与当前架构判断一致：

- backend 可作为迁移起点；
- frontend build 可运行，但质量门禁不通过；
- frontend 还没有自动化行为测试；
- 不因 build 通过而声称产品闭环完成；
- Phase 1 必须先建立 discriminated question union、contract tests 和 answer-isolation tests。

Phase 0 结果已记录，等待用户确认；不自动进入 Phase 1。
