from os.path import abspath, dirname, join


class BaseConfig(object):
    DEBUG = False
    TESTING = False
    BASE_DIR = dirname(dirname(abspath(__file__)))
    UPLOAD_DIR = join(BASE_DIR, 'courses')
    JWT_ALGORITHM = "RS256"
    JWT_ISSUER = "shepherd"
    # JWT_PUBLIC_KEY = """
    # -----BEGIN PUBLIC KEY-----
    # MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0QIB6wP5rGpT7pcKM0uQ
    # bn3FbQI2Xp58vLW+eLISgPvh0EMNuVWMazRfTBGnSxYI2P2F+Yf+O8Ck3JWOpuCD
    # +i0a+RlC7gZdspULHpRYSccOqvRdcMn93nuPxiHJ+zAFuVR6mmDQmkHR3ruFvbQt
    # FWABpbZpqVOlaOUqoyQcp7JGOrrGZZhifS8EE56azvhIm8n2qf+KhKkTq0P71j+4
    # 3h2sZtHM9nrsm/wtyb26xPBwGS1v1d5bWw0D2vhPSCP4HV2DuI6WD6pEN9Axjf5j
    # dG7tGa6GnyPchdDAvlnA1FQiFfkz4NQtL5upmGiz6gBslFlPhZmejlr2RUYd4mbQ
    # 3QIDAQAB
    # -----END PUBLIC KEY-----
    # """
    JWT_PUBLIC_KEY = open('public.pem', 'rb').read()


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class TestingConfig(BaseConfig):
    TESTING = True
