from flask import Blueprint, request, jsonify
import pandas as pd
from models.tabular_model import TabularTradingModel, prepare_features
from rl.agent import RLTradingAgent
import numpy as np
import os

model_api = Blueprint('model_api', __name__)

# Endpoint para predição tabular
@model_api.route('/predict/tabular', methods=['POST'])
def predict_tabular():
    data = request.json
    df = pd.DataFrame([data])
    features = prepare_features(df)
    model = TabularTradingModel()
    pred = model.predict(features)
    return jsonify({'prediction': int(pred[0])})

# Endpoint para predição RL
@model_api.route('/predict/rl', methods=['POST'])
def predict_rl():
    data = request.json
    state = np.array(data['state']).reshape(-1, 1)
    state_size = state.shape[0]
    action_size = 3
    model_path = data.get('model_path')
    agent = RLTradingAgent(state_size, action_size, model_path=model_path)
    action = agent.act(state)
    return jsonify({'action': int(action)})
