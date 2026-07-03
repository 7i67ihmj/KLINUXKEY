from flask import Flask, request, jsonify
import sqlite3
import time
import os
import random
import string
from datetime import datetime

app = Flask(__name__)

# ===== CORS =====
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response
# ===== KẾT THÚC =====

DB_PATH = '/tmp/keys.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS keys
                 (key TEXT PRIMARY KEY,
                  hwid TEXT,
                  created_at INTEGER,
                  expires_at INTEGER,
                  total_executions INTEGER DEFAULT 0,
                  note TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS hwid_resets
                 (hwid TEXT PRIMARY KEY,
                  last_reset INTEGER)''')
    
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    return conn

init_db()

ADMIN_KEY = os.environ.get('ADMIN_KEY', 'hoho_admin_2024')

def generate_key():
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"KLINUX-LUANORI-{random_part}"

@app.route('/api/getkey', methods=['GET'])
def get_key():
    try:
        hwid = request.args.get('hwid', 'unknown')
        
        conn = get_db()
        c = conn.cursor()
        
        c.execute('''SELECT key FROM keys 
                     WHERE hwid = ? AND expires_at > ? 
                     ORDER BY created_at DESC LIMIT 1''', 
                  (hwid, int(time.time())))
        existing = c.fetchone()
        
        if existing:
            conn.close()
            return existing[0]
        
        key_id = generate_key()
        
        while True:
            c.execute('SELECT key FROM keys WHERE key = ?', (key_id,))
            if not c.fetchone():
                break
            key_id = generate_key()
        
        created_at = int(time.time())
        expires_at = created_at + (24 * 3600)
        
        c.execute('INSERT INTO keys (key, hwid, created_at, expires_at, note) VALUES (?, ?, ?, ?, ?)',
                  (key_id, hwid, created_at, expires_at, 'Free Key'))
        
        conn.commit()
        conn.close()
        
        return key_id
        
    except Exception as e:
        print(f"Error: {e}")
        return "ERROR"

@app.route('/api/check_key', methods=['GET', 'POST', 'OPTIONS'])
def check_key():
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        # Lấy key từ GET hoặc POST
        if request.method == 'GET':
            key = request.args.get('key', '').strip()
            hwid = request.args.get('hwid', 'unknown')
        else:
            data = request.json
            key = data.get('key', '').strip()
            hwid = data.get('hwid', 'unknown')
        
        print(f"[CHECK] Key: {key}, HWID: {hwid}")
        
        if not key:
            return jsonify({
                'code': 'INVALID_KEY',
                'message': 'Key is required'
            }), 400
        
        conn = get_db()
        c = conn.cursor()
        
        c.execute('SELECT * FROM keys WHERE key = ?', (key,))
        key_data = c.fetchone()
        
        # Nếu key không tồn tại, tạo key mới
        if not key_data:
            new_key = generate_key()
            created_at = int(time.time())
            expires_at = created_at + (24 * 3600)
            
            while True:
                c.execute('SELECT key FROM keys WHERE key = ?', (new_key,))
                if not c.fetchone():
                    break
                new_key = generate_key()
            
            c.execute('INSERT INTO keys (key, hwid, created_at, expires_at, note) VALUES (?, ?, ?, ?, ?)',
                      (new_key, hwid, created_at, expires_at, 'Auto-generated'))
            
            conn.commit()
            conn.close()
            
            return jsonify({
                'code': 'KEY_VALID',
                'message': 'New key generated',
                'data': {
                    'total_executions': 0,
                    'note': 'Auto-generated',
                    'new_key': new_key
                }
            })
        
        # Kiểm tra hết hạn
        if key_data[3] < time.time():
            new_key = generate_key()
            created_at = int(time.time())
            expires_at = created_at + (24 * 3600)
            
            while True:
                c.execute('SELECT key FROM keys WHERE key = ?', (new_key,))
                if not c.fetchone():
                    break
                new_key = generate_key()
            
            c.execute('INSERT INTO keys (key, hwid, created_at, expires_at, note) VALUES (?, ?, ?, ?, ?)',
                      (new_key, hwid, created_at, expires_at, 'New key after expiry'))
            
            conn.commit()
            conn.close()
            
            return jsonify({
                'code': 'KEY_EXPIRED',
                'message': 'Key expired, new key generated',
                'data': {
                    'new_key': new_key
                }
            })
        
        db_hwid = key_data[1]
        
        # Nếu key chưa gán HWID, gán nó
        if db_hwid == 'unknown' or db_hwid == '':
            c.execute('UPDATE keys SET hwid = ? WHERE key = ?', (hwid, key))
            conn.commit()
            conn.close()
            return jsonify({
                'code': 'KEY_VALID',
                'message': 'Key is valid',
                'data': {
                    'total_executions': 1,
                    'note': key_data[5] or ''
                }
            })
        
        # Nếu HWID khác, tạo key mới
        if db_hwid != hwid:
            new_key = generate_key()
            created_at = int(time.time())
            expires_at = created_at + (24 * 3600)
            
            while True:
                c.execute('SELECT key FROM keys WHERE key = ?', (new_key,))
                if not c.fetchone():
                    break
                new_key = generate_key()
            
            c.execute('INSERT INTO keys (key, hwid, created_at, expires_at, note) VALUES (?, ?, ?, ?, ?)',
                      (new_key, hwid, created_at, expires_at, 'New key for different HWID'))
            
            conn.commit()
            conn.close()
            
            return jsonify({
                'code': 'KEY_HWID_LOCKED',
                'message': 'Key locked to another HWID, new key generated',
                'data': {
                    'new_key': new_key
                }
            })
        
        # Key hợp lệ, cập nhật số lần thực thi
        c.execute('UPDATE keys SET total_executions = total_executions + 1 WHERE key = ?', (key,))
        conn.commit()
        conn.close()
        
        return jsonify({
            'code': 'KEY_VALID',
            'message': 'Key is valid',
            'data': {
                'total_executions': key_data[4] + 1,
                'note': key_data[5] or ''
            }
        })
        
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({
            'code': 'SERVER_ERROR',
            'message': str(e)
        }), 500

@app.route('/api/freeresethwid', methods=['POST', 'GET', 'OPTIONS'])
def free_reset_hwid():
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        if request.method == 'GET':
            hwid = request.args.get('hwid')
            key = request.args.get('key')
        else:
            data = request.json
            hwid = data.get('hwid')
            key = data.get('key')
        
        if not hwid or not key:
            return jsonify({
                'code': 'INVALID_REQUEST',
                'message': 'Missing info'
            }), 400
        
        conn = get_db()
        c = conn.cursor()
        
        c.execute('SELECT hwid FROM keys WHERE key = ?', (key,))
        result = c.fetchone()
        
        if not result:
            conn.close()
            return jsonify({
                'code': 'INVALID_KEY',
                'message': 'Invalid key'
            }), 400
        
        c.execute('SELECT last_reset FROM hwid_resets WHERE hwid = ?', (hwid,))
        reset_data = c.fetchone()
        
        if reset_data:
            last_reset = reset_data[0]
            if time.time() - last_reset < 86400:
                remaining = int(86400 - (time.time() - last_reset))
                hours = remaining // 3600
                minutes = (remaining % 3600) // 60
                return jsonify({
                    'code': 'COOLDOWN_ACTIVE',
                    'message': f'Please wait {hours}h {minutes}m'
                }), 400
        
        c.execute('UPDATE keys SET hwid = ? WHERE key = ?', ('unknown', key))
        
        if reset_data:
            c.execute('UPDATE hwid_resets SET last_reset = ? WHERE hwid = ?', (int(time.time()), hwid))
        else:
            c.execute('INSERT INTO hwid_resets (hwid, last_reset) VALUES (?, ?)', (hwid, int(time.time())))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'HWID reset successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/delete_key', methods=['POST'])
def delete_key():
    try:
        auth = request.headers.get('Authorization')
        if auth != f'Bearer {ADMIN_KEY}':
            return jsonify({
                'code': 'UNAUTHORIZED',
                'message': 'Invalid admin key'
            }), 401
        
        data = request.json
        key = data.get('key')
        
        if not key:
            return jsonify({
                'code': 'INVALID_REQUEST',
                'message': 'Missing key'
            }), 400
        
        conn = get_db()
        c = conn.cursor()
        c.execute('DELETE FROM keys WHERE key = ?', (key,))
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Key deleted successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/list_keys', methods=['GET'])
def list_keys():
    try:
        auth = request.headers.get('Authorization')
        if auth != f'Bearer {ADMIN_KEY}':
            return jsonify({
                'code': 'UNAUTHORIZED',
                'message': 'Invalid admin key'
            }), 401
        
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT * FROM keys ORDER BY created_at DESC')
        keys = c.fetchall()
        conn.close()
        
        return jsonify({
            'keys': [{
                'key': k[0],
                'hwid': k[1],
                'created_at': datetime.fromtimestamp(k[2]).isoformat(),
                'expires_at': datetime.fromtimestamp(k[3]).isoformat(),
                'total_executions': k[4],
                'note': k[5]
            } for k in keys]
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'name': 'HoHo Key System API',
        'version': '1.0.0',
        'key_format': 'KLINUX-LUANORI-XXXXX',
        'status': 'running'
    })

def handler(event, context):
    return app