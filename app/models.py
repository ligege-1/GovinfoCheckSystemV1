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

    # Relationship to DeepCollectionContent
    deep_content_obj = db.relationship('DeepCollectionContent', backref='collection_item', uselist=False, cascade="all, delete-orphan")

    # Relationship to CrawlRule
    rule_id = db.Column(db.Integer, db.ForeignKey('crawl_rule.id'), nullable=True)
    rule = db.relationship('CrawlRule', backref='collection_items')

    def __repr__(self):
        return '<CollectionItem {}>'.format(self.title)

class DeepCollectionContent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text)
    item_id = db.Column(db.Integer, db.ForeignKey('collection_item.id'), unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return '<DeepCollectionContent item_id={}>'.format(self.item_id)

class CrawlRule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256), default='未命名规则') # 规则名称
    site = db.Column(db.String(256), unique=False, index=True) # 站点域名 或 来源名称
    match_type = db.Column(db.String(64), default='domain') # domain 或 source
    title_xpath = db.Column(db.String(1024))
    content_xpath = db.Column(db.String(2048))
    headers_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return '<CrawlRule {}>'.format(self.name or self.site)

class AiEngine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(64), nullable=False) # Service Provider Name (e.g., OpenAI, DeepSeek)
    api_url = db.Column(db.String(256), nullable=False) # API Base URL
    api_key = db.Column(db.String(256), nullable=False) # API Key
    model_name = db.Column(db.String(128), nullable=False) # Model Name (e.g., gpt-4, deepseek-chat)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return '<AiEngine {} - {}>'.format(self.provider, self.model_name)

class CrawlerConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, unique=True) # 爬虫名称
    base_url = db.Column(db.String(512), nullable=False) # 基础URL或搜索URL模板
    method = db.Column(db.String(10), default='GET') # 请求方法
    params_json = db.Column(db.Text) # 请求参数模板 JSON, e.g. {"word": "{keyword}", "pn": "{page_param}"}
    headers_json = db.Column(db.Text) # 请求头 JSON
    
    # 解析规则
    list_selector = db.Column(db.String(256)) # 列表项选择器
    title_selector = db.Column(db.String(256)) # 标题选择器
    url_selector = db.Column(db.String(256)) # URL选择器
    cover_selector = db.Column(db.String(256)) # 封面选择器
    source_selector = db.Column(db.String(256)) # 来源选择器
    date_selector = db.Column(db.String(256)) # 日期选择器
    
    enabled = db.Column(db.Boolean, default=True)
    description = db.Column(db.String(512))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return '<CrawlerConfig {}>'.format(self.name)

@login.user_loader
def load_user(id):
    return db.session.get(User, int(id))
