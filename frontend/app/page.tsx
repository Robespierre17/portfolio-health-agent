import AgentChat from "@/components/AgentChat";
import PortfolioScorer from "@/components/PortfolioScorer";

export default function Home() {
  return (
    <main className="min-h-screen">
      <div className="max-w-3xl mx-auto px-4 py-12 space-y-12">
        <header>
          <h1 className="text-2xl font-semibold text-gray-900">
            Portfolio Health Agent
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            XGBoost risk scorer + Claude LLM agent
          </p>
        </header>

        <div className="h-px bg-gray-200" />

        <PortfolioScorer />

        <div className="h-px bg-gray-200" />

        <AgentChat />
      </div>
    </main>
  );
}
