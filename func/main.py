from flask import Flask, request, jsonify
from common.notion_auth import NotionAuth, require_notion_auth
import os

app = Flask(__name__)

@app.route('/test', methods=['GET'])
@require_notion_auth
def test_endpoint():
    return jsonify({"message": "認証成功！"})

def notion_functions(request):
    return app(request.environ, lambda status, headers, exc_info: None)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080))) 