import os
import sys
from flask import Flask, render_template

# Add project root to path
sys.path.append(os.getcwd())

from app import create_app

app = create_app()

def check_template(template_name, **context):
    print(f"Checking {template_name}...")
    try:
        with app.test_request_context():
            template = app.jinja_env.get_template(template_name)
            
            class MockUser:
                is_authenticated = True
                username = "testuser"
                role = "admin"
            
            ctx = {
                'title': 'Test Title',
                'current_user': MockUser(),
            }
            ctx.update(context)
            
            template.render(**ctx)
            print(f"PASS: {template_name}")
    except Exception as e:
        print(f"FAIL: {template_name}")
        print(e)

if __name__ == "__main__":
    templates = ['index.html', 'base.html', 'collector.html', 'warehouse.html', 'rules.html']
    for t in templates:
        check_template(t)
