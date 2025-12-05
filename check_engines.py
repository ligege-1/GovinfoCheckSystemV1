import json
import requests
from app import create_app, db
from app.models import AiEngine, DeepCollectionContent, CollectionItem
from sqlalchemy import text

app = create_app()

def run_check_engines():
    with app.app_context():
        engines = AiEngine.query.all()
        for e in engines:
            print(f"ID: {e.id}, Provider: {e.provider}, Model: {e.model_name}, Active: {e.is_active}, URL: {e.api_url}")

if __name__ == "__main__":
    run_check_engines()
