from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='user')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def is_admin(self):
        return self.role == 'admin'

class Tool(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    language = db.Column(db.String(100))
    code = db.Column(db.Text)
    github_url = db.Column(db.String(500))
    image_url = db.Column(db.String(300))
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)

class BlogPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    excerpt = db.Column(db.Text)
    content = db.Column(db.Text, nullable=False)
    featured_image = db.Column(db.String(300))
    tags = db.Column(db.String(300))
    published = db.Column(db.Boolean, default=False)
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)

class News(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    excerpt = db.Column(db.Text)
    content = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(300))
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)

class GalleryFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(300), nullable=False)
    stored_filename = db.Column(db.String(300), unique=True, nullable=False)
    file_type = db.Column(db.String(50))
    description = db.Column(db.Text)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    size = db.Column(db.Integer)
