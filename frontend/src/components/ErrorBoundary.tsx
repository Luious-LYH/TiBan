import { Component, type ErrorInfo, type ReactNode } from 'react'
import { AlertTriangle, RotateCcw } from 'lucide-react'
import { v3SafetyNotice } from '../lib/v3Api'

type Props = {
  children: ReactNode
  resetKey?: string
}

type State = {
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('ARIS page safety guard', error, info.componentStack)
  }

  componentDidUpdate(prevProps: Props) {
    if (this.state.error && prevProps.resetKey !== this.props.resetKey) {
      this.setState({ error: null })
    }
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className="page-stack">
        <section className="route-guard-page">
          <AlertTriangle size={34} />
          <div>
            <span className="eyebrow">页面安全保护</span>
            <h2>页面已进入安全降级</h2>
            <p>当前页面渲染时遇到异常。平台保留导航和安全边界，刷新后可继续演示其他模块。</p>
            <button className="button primary" type="button" onClick={() => window.location.reload()}>
              <RotateCcw size={17} /> 重新加载
            </button>
            <small>{v3SafetyNotice}</small>
          </div>
        </section>
      </div>
    )
  }
}
