import pytest

from application.models import Field

expected_order = [
    "entity",
    "name",
    "prefix",
    "reference",
    "category",
    "dataset",
    "description",
    "developer-agreement-type",
    "documentation-url",
    "notes",
    "organisation",
    "permitted-development-right-part",
    "planning-application-category",
    "project",
    "provision-reason",
    "specification",
    "entry-date",
    "start-date",
    "end-date",
]

fields_and_types = {
    "end-date": "datetime",
    "entity": "integer",
    "entry-date": "datetime",
    "name": "string",
    "notes": "text",
    "prefix": "string",
    "reference": "string",
    "start-date": "datetime",
    "description": "string",
    "provision-reason": "string",
    "developer-agreement-type": "string",
    "dataset": "string",
    "organisation": "curie",
    "project": "string",
    "specification": "string",
    "documentation-url": "url",
    "planning-application-category": "string",
    "permitted-development-right-part": "string",
    "category": "curie",
}


@pytest.fixture
def fields():
    from random import shuffle

    fields = []

    for field, datatype in fields_and_types.items():
        fields.append(
            Field(
                field=field,
                name=field.capitalize().replace("-", " "),
                datatype=datatype,
            )
        )

    shuffle(fields)
    return fields


def test_field_ordering(fields):
    ordered = sorted(fields)

    for i, field in enumerate(ordered):
        assert field.field == expected_order[i]
