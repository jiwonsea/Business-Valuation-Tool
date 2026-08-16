from engine.scoring_basis import compare_bases, format_gap_of_gap


def test_comparison_always_labels_both_bases_and_splits_gap_fields() -> None:
    result = compare_bases(
        base={"revenue": 79_070.2667, "op": 61_972.0},
        weighted={"revenue": 77_212.7510, "op": 60_426.2857},
        actual={"revenue": 79_318.6, "op": 60_543.4},
        consensus={"revenue": 83_646.0, "op": 63_659.4},
    )

    assert [row["basis"] for row in result["comparisons"]] == ["base", "weighted"]
    assert set(result) == {"comparisons", "gap_of_gap_base", "gap_of_gap_weighted"}
    rendered = "\n".join(format_gap_of_gap(result))
    assert "`gap_of_gap_base`" in rendered
    assert "`gap_of_gap_weighted`" in rendered


def test_gap_of_gap_never_combines_different_bases() -> None:
    result = compare_bases(
        base={"metric": 110.0},
        weighted={"metric": 90.0},
        actual={"metric": 100.0},
        consensus={"metric": 80.0},
    )
    assert result["gap_of_gap_base"]["metric"] == 0.125
    assert result["gap_of_gap_weighted"]["metric"] == -0.125
