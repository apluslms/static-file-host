from os.path import dirname, join


class Config(object):
    DEBUG = False
    TESTING = False
    BASE_DIR = dirname(__file__)
    STATIC_PATH = join(BASE_DIR, 'static')
    DATABASE_URI = 'sqlite:///' + BASE_DIR + '/static_management.db'


class ProductionConfig(Config):
    DATABASE_URI = 'mysql://user@localhost/static_management'


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
