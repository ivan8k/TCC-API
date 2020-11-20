#!/usr/bin/python3

from flask import Flask, request, Response
from pymongo import MongoClient
import json
import jwt
import time

db_client = MongoClient('mongodb://helix:H3l1xNG@127.0.0.1:27000/?authSource=admin')
db = db_client.SL
users = db.users
entities = db.entities
sectors = db.sectors
sensors = db.sensors

secret_key = ''

app= Flask(__name__)

@app.route('/users', methods=['POST'])
def api_users():
	req = request.get_json()
	if not req:
		return "", 401, {'Content-Type': 'text/plain; charset=utf-8'}
	user_aux = users.find_one({'user': req['user'], 'password': req['password']}, {'_id': False})
	if (user_aux):
		user = json.loads( str(user_aux).replace("'", '"') )
		user['jwt'] = jwt.encode({'username': user['user'], 'permission': user['permission']}, secret_key, algorithm='HS256').decode('utf-8')
		return user
	resp = Response(response="", status=401, mimetype='text/plain')
	return resp

@app.route('/entities/<entity_id>', methods=['GET'])
def api_id(entity_id):
	if request.method == 'GET':
		aux_entities = json.loads( str( entities.find_one( {'entity_id': entity_id}, {'_id': False} ) ).replace("'", '"') )
		aux_entities['sectors'] = []
		aux_sectors = sectors.find( {'entity_id': entity_id}, {'_id': False, 'entity_id': False, 'status': False} )
		for sector in aux_sectors:
			aux_sensors = sensors.find( {'entity_id': entity_id, 'sector_tag': sector['sector_tag'] }, {'_id': False, 'entity_id': False} )
			sector['sensors'] = []
			for sensor in aux_sensors:
				sector['sensors'].append(json.loads(str(sensor).replace("'", '"')))
			aux_entities['sectors'].append(json.loads(str(sector).replace("'", '"')))
		return aux_entities


@app.route('/entities/<entity_id>/finance', methods=['GET'])
def api_id_finance(entity_id):
	if request.method == 'GET':
		aux_entities = json.loads( str( entities.find_one( {'entity_id': entity_id}, {'_id': False, 'kwh_cost': True} ) ).replace("'", '"') )
		aux_entities['power'] = []
		aux_sectors = sectors.find( {'entity_id': entity_id}, {'_id': False, 'power': True} )
		for sector in aux_sectors:
			aux_entities['power'] += json.loads(str(sector).replace("'", '"'))['power']
		return aux_entities

@app.route('/entities/<entity_id>/<int:sector_tag>/power', methods=['GET', 'PATCH'])
def api_id_sector_power(entity_id, sector_tag):
	if request.method == 'PATCH':
		sectors.update_one({'entity_id': entity_id, 'sectors': sector_tag}, {'$push': {'power': json.loads(request.data)} })
		return 'OK'
	else:
		return {'power' : json.loads( str( sectors.find_one( {'entity_id': entity_id, 'sector_tag': sector_tag}, {'_id': False, 'power': True} )['power'] ).replace("'", '"') )}

@app.route('/entities/<entity_id>/<int:sector_tag>/poll', methods=['GET', 'PUT'])
def api_id_sector_poll(entity_id, sector_tag):
	if request.method == 'PUT':
		req = json.loads(request.data)
		sectors.update_one( {'entity_id': entity_id, 'sector_tag': sector_tag}, {'$set': {'min_intensity': req['min_intensity'], 'max_intensity': req['max_intensity']}} )
		return ""
	if request.method == 'GET':
		data = json.loads( str( sectors.find_one( {'entity_id': entity_id, 'sector_tag': sector_tag}, {'_id': False, 'min_intensity': True, 'max_intensity': True} ) ).replace("'", '"') )
		resp = Response(response=str(data['min_intensity']) + '|' + str(data['max_intensity']), status=200, mimetype='text/plain')
		return resp

@app.route('/entities/<entity_id>/time_data/<time_lim>', methods=['GET', 'PATCH'])
def api_id_timedata_tlim(entity_id, time_lim):
	if request.method == 'PATCH':
		sectors.update_one({'entity_id': entity_id, 'sector_tag': int(time_lim)}, {'$push': {'time_data': json.loads(request.data)} })
		return 'OK'
	else:
		if time_lim == 'week':
			time_data_aux = sectors.find( {'entity_id': entity_id}, {'time_data': True, '_id': False} )
			time_data = []
			for td in time_data_aux:
				time_data += json.loads(str(td).replace("'", '"'))['time_data']
			return {'time_data' : time_data}
		elif time_lim == 'month':
			secs_aux = sectors.find( {'entity_id': entity_id}, {'time_data': True, '_id': False, 'min_intensity': True, 'max_intensity': True} )
			secs = []
			for sec in secs_aux:
				secs.append(json.loads(str(sec).replace("'", '"')))
			return {'sectors': secs}

@app.route('/entities/<entity_id>/<int:sector_tag>/<int:sensor_tag>/<field>', methods=['GET', 'PATCH'])
def api_id_sector_sensor_field(entity_id, sector_tag, sensor_tag, field):
	if request.method == 'PATCH':
		sensors.update_one({'entity_id': entity_id, 'sector_tag': sector_tag, 'sensor_tag': sensor_tag}, {'$push': {field: json.loads(request.data)} })
		return 'OK'
	else:
		return {field : json.loads( str( sensors.find_one( {'entity_id': entity_id, 'sector_tag': sector_tag, 'sensor_tag': sensor_tag} )[field] ).replace("'", '"') )}

@app.route('/entities/<entity_id>/status', methods=['GET'])
def api_id_status(entity_id):
	if request.method == 'GET':
		status_aux = sectors.find({'entity_id': entity_id}, {'_id': False, 'sector_tag': True, 'sector': True, 'status': True, 'last_update': True, 'status_code': True})
		status = []
		for aux in status_aux:
			sec = json.loads( str( aux ).replace("'", '"') )
			if not int(time.time()) - sec['last_update'] >= (60 * 20):
				sec['status_code'] = 1
			#else:
			#	sec['status_code'] = 0
			del sec['last_update']
			for i in range(len(sec['status'])):
				s = json.loads( str( sensors.find_one({'entity_id': entity_id, 'sector_tag': sec['sector_tag'], 'sensor_tag': sec['status'][i]['sensor_tag']}, {'_id': False, 'sensor_name': True}) ).replace("'", '"') )
				sec['status'][i]['sensor_name'] = s['sensor_name']
			status.append(sec)
		return {'status_aux': status}

@app.route('/entities/<entity_id>/status/<int:sector_tag>', methods=['PUT'])
def api_id_sector_status(entity_id, sector_tag):
	if request.method == 'PUT':
		sectors.update_one({'entity_id': entity_id, 'sector_tag': sector_tag}, {'$set': {'status_code': json.loads(request.data)['code']}})
		return ""

@app.route('/entities/<entity_id>/status/<int:sector_tag>/<int:sensor_tag>', methods=['PUT'])
def api_id_sector_sensor_status(entity_id, sector_tag, sensor_tag):
	if request.method == 'PUT':
		sectors.update_one({'entity_id': entity_id, 'sector_tag': sector_tag}, {'$set': {'status.$[elem].status_code': json.loads(request.data)['code']}}, array_filters=[{ 'elem.sensor_tag': {'$eq': sensor_tag}}])
		return ""

@app.route('/entities/<entity_id>/<int:sector_tag>/min_intensity', methods=['GET', 'PUT'])
def api_id_field_mtag_stag(entity_id, field, main_tag, sensor_tag):
	if request.method == 'PATCH':
		entities.update_one({'entity_id': entity_id, field+'.main_tag': main_tag, field+'.sensor_tag': sensor_tag}, {'$push': {field: json.loads(request.data)} })
		return 'OK'
	else:
		return {field : json.loads( str( entities.find_one( {'entity_id': entity_id, field+'.main_tag': main_tag, field+'.sensor_tag': sensor_tag} )[field] ).replace("'", '"') )}

app.run(host='172.31.52.230', port=6042, debug=True)

