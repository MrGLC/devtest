from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class ElevatorDemand(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    called_from_floor = db.Column(db.Integer, nullable=False)
    destination_floor = db.Column(db.Integer, nullable=False)
    resting_floor = db.Column(db.Integer, nullable=False)
    hour_of_day = db.Column(db.Integer, nullable=False)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/demand', methods=['POST'])
def record_demand():
    data = request.json
    new_demand = ElevatorDemand(
        called_from_floor=data['called_from_floor'],
        destination_floor=data['destination_floor'],
        resting_floor=data['resting_floor'],
        hour_of_day=datetime.now().hour
    )
    db.session.add(new_demand)
    db.session.commit()
    return jsonify({'message': 'Demand recorded successfully'}), 201

@app.route('/api/demands', methods=['GET'])
def get_demands():
    demands = ElevatorDemand.query.all()
    return jsonify([{
        'id': d.id,
        'timestamp': d.timestamp,
        'called_from_floor': d.called_from_floor,
        'destination_floor': d.destination_floor,
        'resting_floor': d.resting_floor,
        'hour_of_day': d.hour_of_day
    } for d in demands])

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', debug=True) 