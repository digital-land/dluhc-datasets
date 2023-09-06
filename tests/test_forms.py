import pytest
from wtforms import StringField, URLField
from wtforms.form import Form

from application.forms import FormBuilder
from application.models import Field


@pytest.fixture
def app():
    from application.factory import create_app

    app = create_app("config.TestConfig")
    yield app


fields = [
    Field(field="organisation", datatype="curie", name="Orgasnisation"),
    Field(field="prefix", datatype="string", name="Prefix"),
    Field(field="reference", datatype="string", name="Prefix"),
    Field(field="documentation-url", datatype="url", name="Documentation url"),
    Field(field="notes", datatype="text", name="Notes"),
]


def test_form_builder(app):
    with app.test_request_context():
        builder = FormBuilder(fields)
        form = builder.build()
        assert isinstance(form, Form)
        assert isinstance(form.organisation, StringField)
        assert isinstance(form.prefix, StringField)
        assert isinstance(form.notes, StringField)
        assert isinstance(form["documentation-url"], URLField)


def test_form_with_curie_field_passes_validation_for_valid_input(app):
    with app.test_request_context():
        fields = [Field(field="organisation", datatype="curie", name="Organisation")]
        builder = FormBuilder(fields)
        form = builder.build()
        form.organisation.data = "foo:bar"
        form.validate()
        assert form.errors.get("organisation") is None


def test_form_with_curie_field_fails_validation_of_invalid_input(app):
    with app.test_request_context():
        fields = [Field(field="organisation", datatype="curie", name="Organisation")]
        builder = FormBuilder(fields)
        form = builder.build()
        form.organisation.data = "foo"
        form.validate()
        assert form.errors.get("organisation")
        assert (
            form.errors.get("organisation")[0]
            == "organisation is a curie and should be in the format 'namespace:identifier'"
        )
