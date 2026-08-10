import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/** Keeps a render error in one subtree from blanking the whole app. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Render error:", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="rounded-lg border border-error bg-error/10 px-4 py-3 text-sm text-error">
          Something went wrong rendering this view: {this.state.error.message}
        </div>
      );
    }
    return this.props.children;
  }
}
