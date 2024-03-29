import datetime
import random
import json
import re
import os
import uuid
import locale
from marshmallow import ValidationError
import requests
from flask import Blueprint, jsonify, make_response, abort, request, send_file, current_app as app
from backend.extensions import db, socket
from backend.utils import format_datetime, format_date, parse_date, leave_keys, delete_keys, commit, add_and_commit, \
    delete_and_commit
from sqlalchemy import or_, and_, union_all, union, select, literal_column, column, literal, text, desc, not_
from .models import Devices, Messages, Firmwares
import uuid
from .utils import allowed_file, DeviceConnection

api = Blueprint('api', __name__)

# @api.route('/device/<string:unique_id>/<string:token>', methods=["PUT"])
# def api_device_put(unique_id, token):
#     device = Devices.query.filter(Devices.unique_id == unique_id).first()
#     if not device:
#         device = Devices(unique_id=unique_id, token=token, last_connection=datetime.datetime.utcnow())
#         if not add_and_commit(device):
#             return make_response('Unable to add device.', 500)
#     elif device.token != token:
#         return make_response('Incorrect token.', 401)
#     device.last_connection = datetime.datetime.utcnow()
#     commit()
#     try:
#         json_data = request.get_json(force=True)
#     except Exception as err:
#         return make_response(jsonify({'errors': ['Incorrect JSON.'], 'data': None}), 400)
#     print(json_data)

#     response = {'message': None, 'firmware': None}
#     message = Messages.query.filter(Messages.device_id == device.id, Messages.from_device == False).order_by(Messages.date.desc()).first()
#     if message:
#         response['message'] = message.json
#         print(message.id)
#         Messages.query.filter(Messages.device_id == device.id, Messages.from_device == False, Messages.date <= message.date).delete()
#         commit()
#     firmware = Firmwares.query.filter(Firmwares.device_id == device.id).order_by(Firmwares.version.desc()).first()
#     if firmware:
#         response['firmware'] = {'version': firmware.version}
#     return make_response(jsonify(response), 200)
    

# @api.route('/server/<string:unique_id>/<string:token>', methods=["PUT"])
# def api_server_put(unique_id, token):
#     device = DeviceConnection()
#     if not device.authorize(unique_id, token, False):
#         return make_response(jsonify({'errors': ['Device not found.'], 'data': None}), 404)
#     try:
#         payload = request.get_json(force=True)
#     except Exception as err:
#         return make_response(jsonify({'errors': ['Incorrect JSON.'], 'data': None}), 400)
    
#     response = {}
    

#     if 'command' in payload: # Обрабатываем команды
#         device.post_message_server(payload.get('command'))
#     if 'req' in payload: # Обрабатываем запрос данных
#         req = payload.get('req')
#         if req == 'SYSINFO': # Запрос версии прошивки
#             response['system_info'] = device.get_system_info()
#     else:
#         response['commands'] = device.get_messages_server()
#     return make_response(jsonify({'errors': None, 'data': response}), 200)

# @api.route('/server/commands/<string:unique_id>/<string:token>', methods=["POST"])
# def api_server_post(unique_id, token):
#     device = DeviceConnection()
#     if not device.authorize(unique_id, token, False):
#         return make_response(jsonify({'errors': ['Device not found.']}), 404)
#     try:
#         payload = request.get_json(force=True)
#     except Exception as err:
#         return make_response(jsonify({'errors': ['Incorrect JSON.']}), 400)
    
#     response = {}
    
#     if 'command' not in payload: # Обрабатываем команды
#         return make_response(jsonify({'errors': ['Incorrect JSON.']}), 400)
    
#     if device.post_message_server(payload.get('command')):
#         return make_response(jsonify({}), 201)
#     else:
#         return make_response(jsonify({'errors': ['Error adding command.']}), 500)

@api.route('/server/command/<string:unique_id>/<string:token>', methods=["POST"])
def api_server_command_post(unique_id, token):
    device = DeviceConnection()
    if not device.authorize(unique_id, token, False):
        return make_response(jsonify({'errors': ['Device not found.'], 'data': None}), 404)
    
    try:
        payload = request.get_json(force=True)
    except Exception as err:
        return make_response(jsonify({'errors': ['Incorrect JSON.']}), 400)
    if not device.server_post_command(payload):
        return make_response(jsonify({"created": False}), 200)
    return make_response(jsonify({"created": True}), 200)

@api.route('/server/system_info/<string:unique_id>/<string:token>', methods=["GET"])
def api_server_system_info_get(unique_id, token):
    device = DeviceConnection()
    if not device.authorize(unique_id, token, False):
        return make_response(jsonify({'errors': ['Device not found.'], 'data': None}), 404)
    return make_response(jsonify(device.get_system_info()), 200)

@api.route('/server/status/<string:unique_id>/<string:token>', methods=["GET"])
def api_server_status_get(unique_id, token):
    device = DeviceConnection()
    if not device.authorize(unique_id, token, False):
        return make_response(jsonify({'errors': ['Device not found.'], 'data': None}), 404)
    return make_response(jsonify(device.server_get_status()), 200)

@api.route('/server/checkactivity/<string:unique_id>/<string:token>', methods=["GET"])
def api_server_checkactivity_get(unique_id, token):
    device = DeviceConnection()
    if not device.authorize(unique_id, token, False):
        return make_response(jsonify({'errors': ['Device not found.'], 'data': None}), 404)
    return make_response(jsonify({"active": device.server_get_activity()}), 200)

@api.route('/server/checkauth/<string:unique_id>/<string:token>', methods=["GET"])
def api_server_checkauth_get(unique_id, token):
    device = DeviceConnection()
    if device.authorize(unique_id, token, False):
        return make_response(jsonify({}), 200)
    return make_response(jsonify({}), 404)
    
    

@api.route('/firmware/<string:unique_id>/<string:token>', methods=["POST", "GET"])
def api_firmware_put(unique_id, token):
    device = Devices.query.filter(Devices.unique_id == unique_id).first()
    if not device:
        return make_response(jsonify({'errors': ['Device not found.'], 'data': None}), 404)
    elif device.token != token:
        return make_response(jsonify({'errors': ['Incorrect token.'], 'data': None}), 401)
    if request.method == 'POST':
        UPLOAD_FOLDER = app.config.get('firmware_root')
        

        if 'file' not in request.files:
            return make_response(jsonify({'errors': ['File not provided.'], 'data': None}), 400)
        file = request.files['file']
        if file.filename == '':
            return make_response(jsonify({'errors': ['File not provided.'], 'data': None}), 400)
        
        version = request.form.get('version', None)
        try:
            version = int(version)
        except Exception:
            return make_response(jsonify({'errors': ['version is not of type integer.'], 'data': None}), 400)
        # Проверяем чтобы версия была больше чем ранее загруженная
        firmware = Firmwares.query.filter(Firmwares.device_id==device.id, Firmwares.version >= version).first()
        if firmware:
            return make_response(jsonify({'errors': [f'provide incremented version of firmware.'], 'data': None}), 400)
        if file and allowed_file(file.filename):
            id = uuid.uuid4()
            filename = f'{str(id)}.bin' 
            file.save(os.path.join(app.config['config']['firmware_root'], filename))
            firmware = Firmwares(id=id, version=version, device_id=device.id, date=datetime.datetime.utcnow())
            if not add_and_commit(firmware):
                return make_response(jsonify({'errors': ['Unable to add firmware.'], 'data': None}), 500)
            return make_response(jsonify({'errors': None, 'data': {}}), 201)
        
        
        return make_response(jsonify({'errors': ['File extension must be .bin .'], 'data': None}), 400)
    elif request.method == 'GET':
        firmware = Firmwares.query.filter(Firmwares.device_id == device.id).order_by(Firmwares.version.desc()).first()
        if not firmware:
            return make_response(jsonify({'errors': ['Firmware for device not found.'], 'data': None}), 404)
        else:
            firmware.num_of_downloads += 1
            commit()
            path = os.path.join(app.config['config']['firmware_root'], f'{str(firmware.id)}.bin')
            return send_file(path, as_attachment=False)
        

@socket.route('/ws/device/v1')
def ws_device(ws):
    device = DeviceConnection()
    unauthorized_requests = 0
    steps_from_status = 0
    while True:
        received_data = ws.receive(timeout=1)
        payload = None
        if received_data: 
            try:
                payload = json.loads(received_data)
            except Exception:
                ws.send(json.dumps({"err": "BAD_JSON"}))
                continue
        # Запрашиваем авторизацию если она не пройдена
        if not device.is_authorized and not payload:
            print("DEVICE", None, device.is_authorized, payload)
            unauthorized_requests += 1
        elif not device.is_authorized and payload:
            if device.authorize(payload.get("id", None), payload.get("token", None)):
                ws.send(json.dumps({"info": "authorized"}))
                ws.send(json.dumps({"req": "system_info"}))
                ws.send(json.dumps({"req": "status"}))
        elif device.is_authorized:
            print("DEVICE", device.get_device_id(), device.is_authorized, received_data)
            device.update_last_connection()
            _command = device.device_get_command()
            if _command:
                ws.send(json.dumps({'command': _command}))

            if payload:
                if 'system_info' in payload: # Обрабатываем системную информацию
                    device.device_post_system_info(payload.get('system_info', {}))
                if 'status' in payload: # Обрабатываем статус информацию
                    device.device_post_status(payload.get('status', {}))
                    steps_from_status = 0
                if 'req' in payload: # Обрабатываем запрос данных
                    requested_data = payload.get('req')
                    if requested_data == 'fw': # Запрос версии прошивки
                        _firmware = device.device_get_firmware()
                        ws.send(json.dumps({'fw': _firmware}))

        steps_from_status += 1

        if steps_from_status % 30 == 0:
            ws.send(json.dumps({"req": "status"}))
        # Закрываем сокет если за 5 тактов не проведена авторизация
        if unauthorized_requests >= 5:
            ws.close()




    
    