"""Read dataset and field definitions from the published specification files.

The specification is the source of truth for datasets and their fields.
Datasette is downstream of it via the collection pipeline, so a change to the
specification only reaches datasette once that pipeline has run. Reading the
published specification files removes that lag, and means a field can be added
to a dataset within a day of being added to the specification.
"""

import csv
import io

import requests

DEFAULT_SPECIFICATION_URL = "https://files.planning.data.gov.uk/specification"
CSV_URL = "{base_url}/{name}.csv"


class Specification:
    """A lazily fetched view over the published specification CSVs.

    Each CSV is fetched at most once per instance, so a command that looks up
    many fields makes one request rather than one request per field. Create a
    new instance per command run rather than sharing one, so that a long lived
    process never serves stale definitions.
    """

    def __init__(self, base_url=None):
        self.base_url = (base_url or DEFAULT_SPECIFICATION_URL).rstrip("/")
        self.rows = {}

    def _rows(self, name):
        if name not in self.rows:
            url = CSV_URL.format(base_url=self.base_url, name=name)
            response = requests.get(url)
            response.raise_for_status()
            self.rows[name] = list(csv.DictReader(io.StringIO(response.text)))
        return self.rows[name]

    def field(self, field):
        """The specification row for a field, or None if it is not specified."""
        for row in self._rows("field"):
            if row["field"] == field:
                return row
        return None

    def category_datasets(self):
        """The datasets this application manages records for."""
        return [
            row
            for row in self._rows("dataset")
            if row["typology"] == "category"
            and row["realm"] == "dataset"
            and row["dataset"] != "category"
        ]

    def replacement_datasets(self):
        """Datasets which name another dataset as their replacement."""
        return [row for row in self._rows("dataset") if row["replacement-dataset"]]

    def dataset_fields(self, dataset):
        """The fields making up a dataset's schema."""
        return [
            row["field"]
            for row in self._rows("dataset-field")
            if row["dataset"] == dataset
        ]

    def datasets_referencing(self, dataset):
        """Datasets whose schema refers to this dataset, as a field or a field's dataset."""
        return sorted(
            {
                row["dataset"]
                for row in self._rows("dataset-field")
                if dataset in (row["field"], row["field-dataset"])
            }
        )

    def specification_for_dataset(self, dataset):
        """The specification a dataset belongs to, or None."""
        for row in self._rows("specification-field"):
            if row["dataset"] == dataset:
                return row["specification"]
        return None
