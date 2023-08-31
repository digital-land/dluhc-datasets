from wtforms import DateField, IntegerField, StringField, URLField
from wtforms.form import Form

from application.forms import CurieField, FormBuilder


def test_form_builder():
    builder = FormBuilder()

    builder.with_field("organisation", "curie")
    builder.with_field("end-date", "datetime")
    builder.with_field("entity", "integer")
    builder.with_field("prefix", "string")
    builder.with_field("notes", "text")
    builder.with_field("documentation-url", "url")

    form = builder.build()

    assert isinstance(form, Form)
    assert isinstance(form.organisation, CurieField)
    assert isinstance(form["end-date"], DateField)
    assert isinstance(form.entity, IntegerField)
    assert isinstance(form.prefix, StringField)
    assert isinstance(form.notes, StringField)
    assert isinstance(form["documentation-url"], URLField)


def test_form_with_curie_field_passes_validation_for_valid_input():
    builder = FormBuilder()
    builder.with_field("reference", "curie")
    form = builder.build()
    form.reference.data = "foo:bar"
    form.validate()
    assert form.errors.get("reference") is None


def test_form_with_curie_field_fails_validation_of_invalid_input():
    builder = FormBuilder()
    builder.with_field("reference", "curie")
    form = builder.build()
    form.reference.data = "foo"
    form.validate()
    assert form.errors.get("reference")
    assert (
        form.errors.get("reference")[0]
        == "curie should be in the format {namespace}:{identifier}"
    )
