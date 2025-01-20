from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import time
from sqlalchemy.exc import OperationalError

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Building(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    total_floors = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    elevators = db.relationship('Elevator', backref='building', lazy=True)

class Elevator(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    building_id = db.Column(db.Integer, db.ForeignKey('building.id'), nullable=False)
    current_floor = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(50), nullable=False)  # IDLE, MOVING_UP, MOVING_DOWN, MAINTENANCE
    capacity = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    calls = db.relationship('ElevatorCall', backref='elevator', lazy=True)
    resting_positions = db.relationship('RestingPosition', backref='elevator', lazy=True)

class ElevatorCall(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    elevator_id = db.Column(db.Integer, db.ForeignKey('elevator.id'), nullable=False)
    called_from_floor = db.Column(db.Integer, nullable=False)
    destination_floor = db.Column(db.Integer, nullable=False)
    passenger_count = db.Column(db.Integer)
    call_time = db.Column(db.DateTime, nullable=False)
    wait_time_seconds = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class RestingPosition(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    elevator_id = db.Column(db.Integer, db.ForeignKey('elevator.id'), nullable=False)
    floor = db.Column(db.Integer, nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime)
    was_called_while_resting = db.Column(db.Boolean, default=False)
    called_from_floor = db.Column(db.Integer)
    time_to_next_call = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class FloorOccupancy(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    building_id = db.Column(db.Integer, db.ForeignKey('building.id'), nullable=False)
    floor = db.Column(db.Integer, nullable=False)
    occupancy_count = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class DailyPattern(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    building_id = db.Column(db.Integer, db.ForeignKey('building.id'), nullable=False)
    floor = db.Column(db.Integer, nullable=False)
    hour_of_day = db.Column(db.Integer, nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)
    avg_calls_per_hour = db.Column(db.Float)
    avg_occupancy = db.Column(db.Integer)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

def generate_mock_data():
    """
    Generates realistic mock data for an office building with distinct patterns:
    - Morning rush (8:00-10:00): Heavy ground floor to upper floors traffic
    - Morning work (10:00-12:00): Inter-floor movement
    - Lunch time (12:00-14:00): Traffic to/from ground floor and cafeteria
    - Afternoon work (14:00-16:00): Inter-floor movement
    - Evening rush (16:00-18:00): Heavy traffic to ground floor
    - After hours (18:00-8:00): Minimal movement
    """
    import random
    from datetime import datetime, timedelta

    # Clear existing data
    db.session.query(DailyPattern).delete()
    db.session.query(FloorOccupancy).delete()
    db.session.query(RestingPosition).delete()
    db.session.query(ElevatorCall).delete()
    db.session.query(Elevator).delete()
    db.session.query(Building).delete()
    
    # Create a building (5 floors: G + 4 floors)
    building = Building(name="Office Building", total_floors=5)
    db.session.add(building)
    db.session.flush()
    
    elevator = Elevator(
        building_id=building.id,
        current_floor=0,
        status='IDLE',
        capacity=8
    )
    db.session.add(elevator)
    db.session.flush()

    # Floor occupancy distribution
    floor_occupancy = {
        0: 0,    # Ground floor (lobby)
        1: 25,   # Finance & HR
        2: 35,   # Engineering
        3: 30,   # Marketing & Sales
        4: 20    # Executive & Meeting rooms
    }

    # Time blocks with different behavior patterns
    time_blocks = {
        # Morning arrival (ground to offices)
        (8, 10): {
            'source_floors': [0],
            'destination_weights': {0: 0.05, 1: 0.25, 2: 0.3, 3: 0.25, 4: 0.15},
            'calls_per_hour': (15, 25)
        },
        # Morning work
        (10, 12): {
            'source_floors': range(5),
            'destination_weights': {0: 0.1, 1: 0.2, 2: 0.2, 3: 0.2, 4: 0.3},
            'calls_per_hour': (8, 15)
        },
        # Lunch time
        (12, 14): {
            'source_floors': range(1, 5),
            'destination_weights': {0: 0.7, 1: 0.1, 2: 0.1, 3: 0.05, 4: 0.05},
            'calls_per_hour': (20, 30)
        },
        # Afternoon work
        (14, 16): {
            'source_floors': range(5),
            'destination_weights': {0: 0.1, 1: 0.2, 2: 0.2, 3: 0.2, 4: 0.3},
            'calls_per_hour': (8, 15)
        },
        # Evening departure
        (16, 18): {
            'source_floors': range(1, 5),
            'destination_weights': {0: 0.85, 1: 0.05, 2: 0.05, 3: 0.03, 4: 0.02},
            'calls_per_hour': (15, 25)
        },
        # After hours
        (18, 8): {
            'source_floors': range(5),
            'destination_weights': {0: 0.5, 1: 0.15, 2: 0.15, 3: 0.1, 4: 0.1},
            'calls_per_hour': (2, 5)
        }
    }

    base_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    for hour in range(24):
        current_time = base_time + timedelta(hours=hour)
        
        # Find current time block
        time_block = None
        for (start_hour, end_hour), block in time_blocks.items():
            if start_hour <= hour < end_hour or (start_hour > end_hour and (hour >= start_hour or hour < end_hour)):
                time_block = block
                break
        if not time_block:
            time_block = time_blocks[(18, 8)]
        
        # Generate occupancy data
        for floor, base_occupancy in floor_occupancy.items():
            if 8 <= hour < 18:
                actual_occupancy = int(base_occupancy * random.uniform(0.7, 1.0))
            else:
                actual_occupancy = int(base_occupancy * random.uniform(0, 0.15))
            
            occupancy = FloorOccupancy(
                building_id=building.id,
                floor=floor,
                occupancy_count=actual_occupancy,
                timestamp=current_time
            )
            db.session.add(occupancy)
        
        # Generate elevator calls
        num_calls = random.randint(*time_block['calls_per_hour'])
        
        for _ in range(num_calls):
            call_time = current_time + timedelta(minutes=random.randint(0, 59))
            source_floor = random.choice(time_block['source_floors'])
            
            destination_floor = random.choices(
                list(time_block['destination_weights'].keys()),
                list(time_block['destination_weights'].values())
            )[0]
            
            while destination_floor == source_floor:
                destination_floor = random.choices(
                    list(time_block['destination_weights'].keys()),
                    list(time_block['destination_weights'].values())
                )[0]
            
            # Determine optimal resting position based on time of day
            if 8 <= hour < 10:  # Morning arrival
                preferred_rest = 0
            elif 16 <= hour < 18:  # Evening departure
                preferred_rest = 0
            elif 12 <= hour < 14:  # Lunch time
                preferred_rest = 0
            else:  # Other times, prefer middle floors
                preferred_rest = 2
            
            call = ElevatorCall(
                elevator_id=elevator.id,
                called_from_floor=source_floor,
                destination_floor=destination_floor,
                passenger_count=random.randint(1, 3),
                call_time=call_time,
                wait_time_seconds=random.randint(0, 180)
            )
            db.session.add(call)
            
            resting = RestingPosition(
                elevator_id=elevator.id,
                floor=preferred_rest,
                start_time=call_time,
                end_time=call_time + timedelta(minutes=random.randint(5, 15)),
                was_called_while_resting=True,
                called_from_floor=source_floor
            )
            db.session.add(resting)
    
    db.session.commit()

def wait_for_db(retries=5, delay=2):
    for _ in range(retries):
        try:
            db.create_all()
            return True
        except OperationalError:
            time.sleep(delay)
    return False

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/demand', methods=['POST'])
def record_demand():
    try:
        data = request.json
        elevator = Elevator.query.first()
        
        new_call = ElevatorCall(
            elevator_id=elevator.id,
            called_from_floor=data['called_from_floor'],
            destination_floor=data['destination_floor'],
            passenger_count=data.get('passenger_count', 1),
            call_time=datetime.fromisoformat(data.get('timestamp', datetime.now().isoformat())),
            wait_time_seconds=0
        )
        
        new_position = RestingPosition(
            elevator_id=elevator.id,
            floor=data['resting_floor'],
            start_time=datetime.now(),
            was_called_while_resting=True,
            called_from_floor=data['called_from_floor']
        )
        
        if 'floor_occupancy' in data:
            new_occupancy = FloorOccupancy(
                building_id=elevator.building_id,
                floor=data['called_from_floor'],
                occupancy_count=data['floor_occupancy'],
                timestamp=datetime.now()
            )
            db.session.add(new_occupancy)
        
        db.session.add(new_call)
        db.session.add(new_position)
        db.session.commit()
        
        return jsonify({'message': 'Demand recorded successfully'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/v1/analytics/patterns', methods=['GET'])
def get_patterns():
    try:
        elevator = Elevator.query.first()
        if not elevator:
            return jsonify([])
            
        calls = ElevatorCall.query.filter_by(elevator_id=elevator.id).all()
        hourly_data = [{'calls': 0, 'occupancy': 0} for _ in range(24)]
        
        for call in calls:
            hour = call.call_time.hour
            hourly_data[hour]['calls'] += 1
            
        return jsonify([{
            'hour_of_day': hour,
            'avg_calls_per_hour': data['calls'],
            'avg_occupancy': data['occupancy']
        } for hour, data in enumerate(hourly_data)])
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/v1/floor-occupancy', methods=['GET'])
def get_floor_occupancy():
    return jsonify([])  # Placeholder for now

def calculate_resting_success_rate(elevator_id):
    resting_positions = RestingPosition.query.filter_by(
        elevator_id=elevator_id,
        was_called_while_resting=True
    ).all()
    
    success_count = sum(1 for pos in resting_positions 
                       if pos.floor == pos.called_from_floor)
    
    return success_count / len(resting_positions) if resting_positions else 0

@app.route('/api/v1/analytics/success-rate', methods=['GET'])
def get_success_rate():
    elevator_id = request.args.get('elevator_id', type=int)
    if not elevator_id:
        return jsonify({'error': 'elevator_id required'}), 400
        
    success_rate = calculate_resting_success_rate(elevator_id)
    return jsonify({'success_rate': success_rate})

with app.app_context():
    if wait_for_db():
        if Building.query.count() == 0:
            generate_mock_data()

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True) 