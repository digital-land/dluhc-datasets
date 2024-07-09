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
    PLATFORM_URL = os.getenv("PLATFORM_URL")
    PLANNING_DATA_DESIGN_URL = os.getenv("PLANNING_DATA_DESIGN_URL")


class DevelopmentConfig(Config):
    DEBUG = False
    ENV = "development"
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_RECORD_QUERIES = True
    DEBUG_TB_INTERCEPT_REDIRECTS = False
    AUTHENTICATION_ON = True


class TestConfig(Config):
    ENV = "test"
    DEBUG = True
    TESTING = True
