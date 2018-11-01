import os


VISUALIZE_UPLOAD_FOLDER = 'annotation_uploads'
RAW_UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = set(['csv'])
DATA_DIR = 'static/data/'
APTV_OUTPUT_DIR = os.path.join(DATA_DIR, 'aptv')
EXPORT_OUTPUT_DIR = os.path.join(DATA_DIR, 'export')
RAW_OUTPUT_DIR = os.path.join(DATA_DIR, 'output')
REDIS = {
    'host': 'localhost',
    'port': 6379,
    'db': 0,
}
TEMPLATES_AUTO_RELOAD = True
# change this in prod configuration
SECRET_KEY='\xf7\xe8wQ\x1b\xa1\x1ecmXe\x11\xdbb\x15\x9d\x9b\xd0\x9bhf\x1dqL'
