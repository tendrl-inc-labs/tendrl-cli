from tendrl_cli.common import extract_list


def test_bare_array():
    records, total = extract_list([{"id": 1}])
    assert records == [{"id": 1}]
    assert total is None


def test_data_total_envelope():
    records, total = extract_list({"data": [{"id": 1}], "total": 42})
    assert records == [{"id": 1}]
    assert total == 42


def test_named_resource_envelope():
    records, total = extract_list({"messages": [{"id": 1}], "next_cursor": "20"}, "messages")
    assert records == [{"id": 1}]
    assert total is None


def test_named_key_wins_over_data():
    payload = {"runs": [{"id": "r1"}], "total": 7}
    records, total = extract_list(payload, "runs")
    assert records == [{"id": "r1"}]
    assert total == 7


def test_unknown_shape_is_empty():
    records, total = extract_list({"weird": "thing"})
    assert records == []
    assert total is None
