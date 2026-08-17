# -*- coding: utf-8 -*-
import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    APP_ROOT = os.path.abspath(os.path.dirname(__file__))
    PROJECT_ROOT = os.path.abspath(os.path.join(APP_ROOT, os.pardir))
    SECRET_KEY = os.getenv("SECRET_KEY")
    DATABASE_URL = os.getenv("DATABASE_URL")
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://")
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_RECORD_QUERIES = False
    DEBUG = False
    GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
    GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
    SAFE_URLS = set(os.getenv("SAFE_URLS", "").split(","))
    AUTHENTICATION_ON = True
    DATASETS_REPO_NAME = os.getenv("DATASETS_REPO_NAME")
    DATASETS_REPO_REGISTERS_PATH = os.getenv("DATASETS_REPO_REGISTERS_PATH")
    SPECIFICATION_REPO_URL = os.getenv("SPECIFICATION_REPO_URL")
    # where the built specification csv files are published
    SPECIFICATION_URL = os.getenv(
        "SPECIFICATION_URL", "https://files.planning.data.gov.uk/specification"
    )
    PLATFORM_URL = os.getenv("PLATFORM_URL")
    PLANNING_DATA_DESIGN_URL = os.getenv("PLANNING_DATA_DESIGN_URL")
    WIKIDATA_PREFIX_DATASETS = set(
        [
            "development-corporation",
            "national-park-authority",
            "nonprofit",
            "public-authority",
            "passenger-transport-executive",
            "regional-park-authority",
            "waste-authority",
        ]
    )
    # Datasets this service manages which are not category datasets, and so are
    # not picked up by the typology rule in Specification.managed_datasets.
    # Naming one here is how a non category dataset gets added, so that it is a
    # reviewed change picked up on the next restart, rather than a command run
    # by hand against the deployed database.
    ADDITIONAL_DATASETS = set(
        [
            "company",
        ]
    )


class DevelopmentConfig(Config):
    DEBUG = False
    ENV = "development"
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_RECORD_QUERIES = True
    DEBUG_TB_INTERCEPT_REDIRECTS = False
    AUTHENTICATION_ON = False


class TestConfig(Config):
    ENV = "test"
    DEBUG = True
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
