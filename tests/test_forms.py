from wtforms import DateField, IntegerField, StringField, URLField
from wtforms.form import Form

from application.forms import CurieField, FormBuilder


def test_form_builder():
    builder = FormBuilder()

    builder.with_field("curie")
    builder.with_field("datetime")
    builder.with_field("integer")
    builder.with_field("string")
    builder.with_field("text")
    builder.with_field("url")

    form = builder.build()

    assert isinstance(form, Form)
    assert isinstance(form.curie, CurieField)
    assert isinstance(form.datetime, DateField)
    assert isinstance(form.integer, IntegerField)
    assert isinstance(form.string, StringField)
    assert isinstance(form.text, StringField)
    assert isinstance(form.url, URLField)


def test_form_with_curie_field_passes_validation_for_valid_input():
    builder = FormBuilder()
    builder.with_field("curie")
    form = builder.build()
    form.curie.data = "foo:bar"
    form.validate()
    assert form.errors.get("curie") is None


def test_form_with_curie_field_fails_validation_of_invalid_input():
    builder = FormBuilder()
    builder.with_field("curie")
    form = builder.build()
    form.curie.data = "foo"
    form.validate()
    assert form.errors.get("curie")
    assert (
        form.errors.get("curie")[0]
        == "curie should be in the format {namespace}:{identifier}"
    )
