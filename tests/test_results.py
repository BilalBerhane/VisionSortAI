from analyze_and_backup.results import ResultRecord, search_documents


def _doc(filename, extracted_text="", category="", timestamp=""):
    return ResultRecord(
        filename=filename,
        kind="document",
        stored_at="2026-08-13T00:00:00+00:00",
        metadata={"extracted_text": extracted_text, "category": category, "timestamp": timestamp},
    )


def test_date_range_includes_boundaries():
    records = {
        "a.jpg": _doc("a.jpg", timestamp="2013:07:27 21:59:13"),
        "b.jpg": _doc("b.jpg", timestamp="2014:01:01 00:00:00"),
        "c.jpg": _doc("c.jpg", timestamp="2015:12:31 23:59:59"),
    }
    results = search_documents(records, date_from="2013-07-27", date_to="2014-01-01")
    names = {r.filename for r in results}
    assert names == {"a.jpg", "b.jpg"}


def test_date_range_excludes_outside_window():
    records = {
        "a.jpg": _doc("a.jpg", timestamp="2010:01:01 00:00:00"),
        "b.jpg": _doc("b.jpg", timestamp="2020:01:01 00:00:00"),
    }
    results = search_documents(records, date_from="2013-01-01", date_to="2015-01-01")
    assert results == []


def test_date_only_filter_excludes_docs_with_no_timestamp():
    records = {"a.jpg": _doc("a.jpg", timestamp="")}
    results = search_documents(records, date_from="2013-01-01", date_to="2015-01-01")
    assert results == []


def test_text_query_matches_extracted_text_or_category():
    records = {
        "a.jpg": _doc("a.jpg", extracted_text="Total: $12.34", category="receipt"),
        "b.jpg": _doc("b.jpg", extracted_text="Dear Sir or Madam", category="letter"),
    }
    assert [r.filename for r in search_documents(records, query="receipt")] == ["a.jpg"]
    assert [r.filename for r in search_documents(records, query="dear")] == ["b.jpg"]


def test_no_filters_returns_all_documents():
    records = {"a.jpg": _doc("a.jpg"), "b.jpg": _doc("b.jpg")}
    assert len(search_documents(records)) == 2


def test_combined_text_and_date_filter():
    records = {
        "a.jpg": _doc("a.jpg", extracted_text="Total: $12.34", timestamp="2013:07:27 21:59:13"),
        "b.jpg": _doc("b.jpg", extracted_text="Total: $99.00", timestamp="2020:01:01 00:00:00"),
    }
    results = search_documents(records, query="total", date_from="2013-01-01", date_to="2015-01-01")
    assert [r.filename for r in results] == ["a.jpg"]
