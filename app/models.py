from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db, login

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    name = db.Column(db.String(64))
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return '<User {}>'.format(self.username)

class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    description = db.Column(db.String(255))
    users = db.relationship('User', backref='role', lazy='dynamic')

    def __repr__(self):
        return '<Role {}>'.format(self.name)

class SystemSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), unique=True, index=True)
    value = db.Column(db.Text)
    description = db.Column(db.String(255))

    def __repr__(self):
        return '<SystemSetting {}: {}>'.format(self.key, self.value)

class CollectionItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    keyword = db.Column(db.String(128), index=True)
    title = db.Column(db.String(512))
    cover = db.Column(db.String(1024))
    url = db.Column(db.String(1024), unique=False, index=True)
    source = db.Column(db.String(256))
    deep_collected = db.Column(db.Boolean, default=False)
    deep_content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return '<CollectionItem {}>'.format(self.title)

class CrawlRule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    site = db.Column(db.String(256), unique=True, index=True)
    title_xpath = db.Column(db.String(1024))
    content_xpath = db.Column(db.String(2048))
    headers_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return '<CrawlRule {}>'.format(self.site)

@login.user_loader
def load_user(id):
    return db.session.get(User, int(id))
