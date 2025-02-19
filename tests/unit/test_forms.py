import pytest
from wtforms import StringField, URLField
from wtforms.form import Form

from application.forms import FormBuilder
from application.models import Field


@pytest.fixture
def app():
    from application.factory import create_app

    app = create_app("application.config.TestConfig")
    yield app


fields = [
    Field(field="organisation", datatype="curie", name="Organisation"),
    Field(field="prefix", datatype="string", name="Prefix"),
    Field(field="reference", datatype="string", name="Reference"),
    Field(field="documentation-url", datatype="url", name="Documentation url"),
    Field(field="notes", datatype="text", name="Notes"),
]


def test_form_builder(app):
    with app.test_request_context():
        builder = FormBuilder(fields)
        form = builder.build()
        assert isinstance(form, Form)
        assert isinstance(form.organisation, StringField)
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


def test_form_required_fields(app):
    with app.test_request_context():
        fields = [
            Field(field="name", datatype="string", name="Name"),
            Field(field="reference", datatype="string", name="Reference"),
        ]
        builder = FormBuilder(fields)
        form = builder.build()

        form.name.data = None
        form.reference.data = None
        form.validate()

        assert form.errors.get("name")
        assert form.errors.get("name")[0] == "This field is required."

        assert form.errors.get("reference")
        assert form.errors.get("reference")[0] == "This field is required."


def test_form_can_set_reference_not_required(app):
    with app.test_request_context():
        fields = [
            Field(field="reference", datatype="string", name="Reference"),
        ]
        builder = FormBuilder(fields, require_reference=False)
        form = builder.build()

        form.reference.data = None
        form.validate()

        assert form.errors.get("reference") is None
