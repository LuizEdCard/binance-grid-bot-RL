#!/usr/bin/env python3
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def hello():
    return 'Flask está funcionando!'

@app.route('/test')
def test():
    return jsonify({'status': 'ok', 'message': 'API funcionando'})

if __name__ == '__main__':
    print('Iniciando servidor de teste na porta 8080...')
    print('Acesse: http://127.0.0.1:8080')
    app.run(host='0.0.0.0', port=8080, debug=False)