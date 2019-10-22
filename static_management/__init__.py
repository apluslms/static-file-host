import logging
from functools import partial

from flask import Flask
import jwt

from static_management import config
from .utils import ImproperlyConfigured

logger = logging.getLogger(__name__)

__version__ = '1.0.0'

# config = {
#     "development": "static_management.config.DevelopmentConfig",
#     "testing": "static_management.config.TestingConfig",
#     "default": "static_management.config.DevelopmentConfig"
# }


# def configure_app(app):
#     config_name = os.getenv('FLASK_CONFIGURATION', 'default')
#     app.config.from_object(config[config_name])  # object-based default configuration
#     # app.config.from_pyfile('config.py', silent=True)  # instance-folders configuration


app = Flask(__name__)
app.config.from_object(config.DevelopmentConfig)


# ----------------------------------------------------------------------------------------------------------------------
# JWT Authentication

def setting_in_bytes(app_instance, name):
    value = app_instance.config.get(name)
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode('utf-8')
    raise ImproperlyConfigured(
        "Value for settings.%s is not bytes or str."
        % (name,))


def prepare_decoder(app_instance):
    options = {'verify_' + k: True for k in ('iat', 'iss')}
    options.update({'require_' + k: True for k in ('iat',)})
    jwt_issuer = app_instance.config.get('JWT_ISSUER')
    if jwt_issuer:
        options['issuer'] = jwt_issuer

    if app_instance.config.get('JWT_PUBLIC_KEY'):
        try:
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives.serialization import load_pem_public_key
        except ImportError as error:
            raise ImproperlyConfigured(
                "Require `cryptography` when using settings.JWT_PUBLIC_KEY: %s"
                % (error,))
        pem = setting_in_bytes(app_instance, 'JWT_PUBLIC_KEY')
        try:
            key = load_pem_public_key(pem, backend=default_backend())
        except ValueError as error:
            raise ImproperlyConfigured(
                "Invalid public key in JWT_PUBLIC_KEY: %s"
                % (error,))
        return partial(jwt.decode,
                       key=key,
                       algorithms=app_instance.config.get('JWT_ALGORITHM'),
                       **options)
    return None








