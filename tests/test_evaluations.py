import pytest

from scripts.eval_engagement import run_engagement_benchmark
from scripts.eval_retrieval import run_retrieval_benchmark


def test_retrieval_benchmark_supports_claim():
    result = run_retrieval_benchmark()

    assert result["baseline_top1_accuracy"] == pytest.approx(0.8)
    assert result["rag_top1_accuracy"] == pytest.approx(1.0)
    assert result["relative_top1_lift_percent"] >= 25.0
    assert all(row["rag_top1_topic"] == row["expected_topic"] for row in result["rows"])


@pytest.mark.asyncio
async def test_engagement_benchmark_supports_estimated_claim():
    result = await run_engagement_benchmark()

    assert result["agent_average_score"] > result["baseline_average_score"]
    assert result["relative_lift_percent"] >= 30.0
    assert all(row["llm_provider"] == "local_fallback" for row in result["rows"])
