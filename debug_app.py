from app import create_app
import traceback

try:
    app = create_app()
    app.config['TESTING'] = True
    # app.config['PROPAGATE_EXCEPTIONS'] = True # Default in testing

    with app.test_client() as client:
        print("Attempting to fetch /")
        try:
            response = client.get('/')
            print(f"Status: {response.status_code}")
            if response.status_code == 500:
                print("Got 500, response data:")
                # print(response.data.decode('utf-8'))
        except Exception:
            traceback.print_exc()

        print("Attempting to fetch /static/layui/css/layui.css")
        try:
            response = client.get('/static/layui/css/layui.css')
            print(f"Status: {response.status_code}")
        except Exception:
            traceback.print_exc()
            
except Exception:
    traceback.print_exc()
