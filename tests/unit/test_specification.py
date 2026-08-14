import pytest

from application.specification import Specification

DATASET_CSV = """dataset,name,typology,realm,end-date,replacement-dataset,consideration,entity-minimum,entity-maximum
design-code-rule-category,Design code rule category,category,dataset,,,design-codes,640100,640999
design-code-feature,Design code feature,category,dataset,,,design-codes,641000,641999
local-plan-event,Local plan event,category,dataset,2026-07-13,plan-event,,700000,700999
category,Category,category,dataset,,,,1,2
conservation-area,Conservation area,geography,dataset,,,,3,4
"""

DATASET_FIELD_CSV = """dataset,field,field-dataset
design-code-rule-category,name,
design-code-rule-category,design-code-feature,design-code-feature
design-code-feature,name,
design-code-feature,reference,
"""

FIELD_CSV = """field,name,datatype,description
name,Name,string,The name of the record
design-code-feature,Design code feature,string,
"""

SPECIFICATION_FIELD_CSV = """specification,dataset,field
design-code,design-code-rule-category,name
design-code,design-code-feature,name
"""

CSVS = {
    "dataset": DATASET_CSV,
    "dataset-field": DATASET_FIELD_CSV,
    "field": FIELD_CSV,
    "specification-field": SPECIFICATION_FIELD_CSV,
}


class FakeResponse:
    def __init__(self, text):
        self.content = text.encode("utf-8")

    def raise_for_status(self):
        pass


@pytest.fixture
def requested():
    return []


@pytest.fixture
def specification(monkeypatch, requested):
    def fake_get(url, **kwargs):
        requested.append(url)
        name = url.rsplit("/", 1)[-1].removesuffix(".csv")
        return FakeResponse(CSVS[name])

    monkeypatch.setattr("application.specification.requests.get", fake_get)
    return Specification()


def test_csvs_are_read_from_the_published_specification_files(specification, requested):
    specification.field("name")

    assert requested == ["https://files.planning.data.gov.uk/specification/field.csv"]


def test_base_url_can_be_overridden(monkeypatch, requested):
    def fake_get(url, **kwargs):
        requested.append(url)
        return FakeResponse(FIELD_CSV)

    monkeypatch.setattr("application.specification.requests.get", fake_get)
    Specification("https://example.com/specification/").field("name")

    assert requested == ["https://example.com/specification/field.csv"]


def test_category_datasets_excludes_other_typologies_and_the_category_dataset(
    specification,
):
    datasets = [row["dataset"] for row in specification.category_datasets()]

    assert "design-code-rule-category" in datasets
    assert "design-code-feature" in datasets
    assert "conservation-area" not in datasets
    assert "category" not in datasets


def test_dataset_fields_returns_the_schema_for_a_dataset(specification):
    assert specification.dataset_fields("design-code-rule-category") == [
        "name",
        "design-code-feature",
    ]


def test_dataset_fields_is_empty_for_an_unspecified_dataset(specification):
    assert specification.dataset_fields("not-a-dataset") == []


def test_field_returns_datatype_and_description(specification):
    field = specification.field("name")

    assert field["datatype"] == "string"
    assert field["description"] == "The name of the record"


def test_field_returns_none_when_not_specified(specification):
    assert specification.field("not-a-field") is None


def test_replacement_datasets_only_returns_datasets_with_a_replacement(specification):
    replacements = specification.replacement_datasets()

    assert [row["dataset"] for row in replacements] == ["local-plan-event"]
    assert replacements[0]["replacement-dataset"] == "plan-event"


def test_datasets_referencing_matches_field_and_field_dataset(specification):
    assert specification.datasets_referencing("design-code-feature") == [
        "design-code-rule-category",
    ]


def test_specification_for_dataset(specification):
    assert specification.specification_for_dataset("design-code-feature") == (
        "design-code"
    )
    assert specification.specification_for_dataset("not-a-dataset") is None


def test_csvs_are_fetched_with_a_timeout(monkeypatch):
    """These run ahead of the app starting, so a stalled connection must not hang."""
    calls = []

    def fake_get(url, **kwargs):
        calls.append(kwargs)
        return FakeResponse(FIELD_CSV)

    monkeypatch.setattr("application.specification.requests.get", fake_get)
    Specification().field("name")

    assert calls[0]["timeout"] is not None


def test_csvs_are_decoded_as_utf_8(monkeypatch):
    """requests falls back to ISO-8859-1 for text/* without a charset."""
    csv_with_utf_8 = (
        "field,name,datatype,description\n"
        "name,Name,string,The record’s name — as published\n"
    )

    class NoCharsetResponse(FakeResponse):
        encoding = "ISO-8859-1"

    monkeypatch.setattr(
        "application.specification.requests.get",
        lambda url, **kwargs: NoCharsetResponse(csv_with_utf_8),
    )

    field = Specification().field("name")

    assert field["description"] == "The record’s name — as published"


def test_each_csv_is_only_fetched_once(specification, requested):
    specification.field("name")
    specification.field("design-code-feature")
    specification.field("another")

    assert len(requested) == 1
