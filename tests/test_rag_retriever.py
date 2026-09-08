from src.rag_retriever import get_retriever


def test_sodium_query_retrieves_sodium_passage():
    results = get_retriever().retrieve("is this high in sodium", goal="lower_sodium")
    assert len(results) > 0
    assert any("sodium" in r.text.lower() for r in results)
    assert all(r.url.startswith("https://www.fda.gov") for r in results)


def test_low_score_results_are_filtered_out():
    results = get_retriever().retrieve("xyzzy unrelated nonsense query", min_score=0.3)
    assert results == []


def test_every_passage_has_citation_metadata():
    retriever = get_retriever()
    for passage in retriever._passages:
        assert passage["title"]
        assert passage["section"]
        assert passage["url"]
