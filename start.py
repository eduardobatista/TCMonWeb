import os
from appp import create_app

app = create_app(debug=True)

with app.app_context():
    pass

if __name__ == '__main__':
    app.run(host='0.0.0.0',port=5000)