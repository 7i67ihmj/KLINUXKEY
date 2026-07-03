from flask import Flask, request, jsonify
import sqlite3
import time
import os
import random
import string
from datetime import datetime

app = Flask(__name__)

# Database path cho Vercel
DB_PATH = '/tmp/keys.db'

def init_db():
    """Khởi tạo database"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Bảng keys
    c.execute('''CREATE TABLE IF NOT EXISTS keys
                 (key TEXT PRIMARY KEY,
                  hwid TEXT,
                  created_at INTEGER,
                  expires_at INTEGER,
                  total_executions INTEGER DEFAULT 0,
                  note TEXT)''')
    
    # Bảng hwid_resets
    c.execute('''CREATE TABLE IF NOT EXISTS hwid_resets
                 (hwid TEXT PRIMARY KEY,
                  last_reset INTEGER)''')
    
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    return conn

# Khởi tạo database
init_db()

# Admin key
ADMIN_KEY = os.environ.get('ADMIN_KEY', 'LuanOri04')

def generate_key():
    """
    Tạo key theo format: KLINUX-LUANORI-XXXXX
    Trong đó XXXXX là 5 ký tự random (chữ hoa và số)
    """
    # Tạo 5 ký tự random (A-Z, 0-9)
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"KLINUX-LUANORI-{random_part}"

def generate_custom_key(suffix_length=5):
    """
    Tạo key với suffix có độ dài tùy chỉnh
    """
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=suffix_length))
    return f"KLINUX-LUANORI-{random_part}"

@app.route('/api/getkey', methods=['GET'])
def get_key():
    """
    Lấy key - tương thích với script
    URL: /api/getkey?hwid=1783082342.7401164
    Trả về: KLINUX-LUANORI-ABC12
    """
    try:
        hwid = request.args.get('hwid', 'unknown')
        
        print(f"[GETKEY] HWID: {hwid}")
        
        conn = get_db()
        c = conn.cursor()
        
        # Kiểm tra xem HWID đã có key chưa (chưa hết hạn)
        c.execute('''SELECT key FROM keys 
                     WHERE hwid = ? AND expires_at > ? 
                     ORDER BY created_at DESC LIMIT 1''', 
                  (hwid, int(time.time())))
        existing = c.fetchone()
        
        if existing:
            conn.close()
            return existing[0]
        
        # Tạo key mới theo format
        key_id = generate_key()
        
        # Đảm bảo key là duy nhất
        while True:
            c.execute('SELECT key FROM keys WHERE key = ?', (key_id,))
            if not c.fetchone():
                break
            key_id = generate_key()
        
        # Key hết hạn sau 24 giờ
        created_at = int(time.time())
        expires_at = created_at + (24 * 3600)  # 24 hours
        
        c.execute('INSERT INTO keys (key, hwid, created_at, expires_at, note) VALUES (?, ?, ?, ?, ?)',
                  (key_id, hwid, created_at, expires_at, 'Free Key'))
        
        conn.commit()
        conn.close()
        
        return key_id
        
    except Exception as e:
        print(f"Error in get_key: {e}")
        return "ERROR"

@app.route('/api/generate_key', methods=['POST'])
def generate_key_admin():
    """
    Tạo key mới với format tùy chỉnh (admin)
    Body: {"duration": 24, "note": "Premium", "suffix_length": 5}
    """
    try:
        auth = request.headers.get('Authorization')
        if auth != f'Bearer {ADMIN_KEY}':
            return jsonify({
                'code': 'UNAUTHORIZED',
                'message': 'Invalid admin key'
            }), 401
        
        data = request.json
        duration_hours = data.get('duration', 24)
        note = data.get('note', '')
        suffix_length = data.get('suffix_length', 5)
        
        # Tạo key
        key_id = generate_custom_key(suffix_length)
        
        # Đảm bảo key duy nhất
        conn = get_db()
        c = conn.cursor()
        
        while True:
            c.execute('SELECT key FROM keys WHERE key = ?', (key_id,))
            if not c.fetchone():
                break
            key_id = generate_custom_key(suffix_length)
        
        created_at = int(time.time())
        expires_at = created_at + (duration_hours * 3600)
        
        c.execute('INSERT INTO keys (key, hwid, created_at, expires_at, note) VALUES (?, ?, ?, ?, ?)',
                  (key_id, 'unknown', created_at, expires_at, note))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'key': key_id,
            'format': 'KLINUX-LUANORI-XXXXX',
            'expires_in_hours': duration_hours,
            'created_at': datetime.fromtimestamp(created_at).isoformat(),
            'expires_at': datetime.fromtimestamp(expires_at).isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/generate_bulk_keys', methods=['POST'])
def generate_bulk_keys():
    """
    Tạo nhiều key cùng lúc (admin)
    Body: {"count": 10, "duration": 24, "note": "Bulk keys"}
    """
    try:
        auth = request.headers.get('Authorization')
        if auth != f'Bearer {ADMIN_KEY}':
            return jsonify({
                'code': 'UNAUTHORIZED',
                'message': 'Invalid admin key'
            }), 401
        
        data = request.json
        count = data.get('count', 5)
        duration_hours = data.get('duration', 24)
        note = data.get('note', 'Bulk keys')
        
        if count > 100:
            return jsonify({
                'success': False,
                'error': 'Maximum 100 keys per request'
            }), 400
        
        keys = []
        conn = get_db()
        c = conn.cursor()
        
        created_at = int(time.time())
        expires_at = created_at + (duration_hours * 3600)
        
        for i in range(count):
            key_id = generate_key()
            
            # Đảm bảo key duy nhất
            while True:
                c.execute('SELECT key FROM keys WHERE key = ?', (key_id,))
                if not c.fetchone():
                    break
                key_id = generate_key()
            
            c.execute('INSERT INTO keys (key, hwid, created_at, expires_at, note) VALUES (?, ?, ?, ?, ?)',
                      (key_id, 'unknown', created_at, expires_at, f"{note} #{i+1}"))
            
            keys.append(key_id)
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'count': count,
            'keys': keys,
            'format': 'KLINUX-LUANORI-XXXXX'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/check_key', methods=['POST'])
def check_key():
    """Kiểm tra key"""
    try:
        data = request.json
        key = data.get('key', '').strip()
        hwid = data.get('hwid', 'unknown')
        
        print(f"[CHECK_KEY] Key: {key}, HWID: {hwid}")
        
        if not key:
            return jsonify({
                'code': 'INVALID_KEY',
                'message': 'Key is required'
            }), 400
        
        # Kiểm tra format key
        if not key.startswith('KLINUX-LUANORI-'):
            return jsonify({
                'code': 'INVALID_KEY',
                'message': 'Invalid key format'
            }), 400
        
        conn = get_db()
        c = conn.cursor()
        
        c.execute('SELECT * FROM keys WHERE key = ?', (key,))
        key_data = c.fetchone()
        
        if not key_data:
            conn.close()
            return jsonify({
                'code': 'INVALID_KEY',
                'message': 'Key không hợp lệ'
            }), 400
        
        # Kiểm tra hết hạn
        if key_data[3] < time.time():
            conn.close()
            return jsonify({
                'code': 'KEY_EXPIRED',
                'message': 'Key đã hết hạn'
            }), 400
        
        # Kiểm tra HWID
        db_hwid = key_data[1]
        
        if db_hwid == 'unknown' or db_hwid == '':
            c.execute('UPDATE keys SET hwid = ? WHERE key = ?', (hwid, key))
            conn.commit()
            conn.close()
            
            c.execute('UPDATE keys SET total_executions = total_executions + 1 WHERE key = ?', (key,))
            conn.commit()
            
            return jsonify({
                'code': 'KEY_VALID',
                'message': 'Key hợp lệ',
                'data': {
                    'total_executions': 1,
                    'note': key_data[5] or ''
                }
            })
        
        if db_hwid != hwid:
            conn.close()
            return jsonify({
                'code': 'KEY_HWID_LOCKED',
                'message': 'Key đã bị khóa với HWID khác'
            }), 400
        
        # Cập nhật số lần thực thi
        c.execute('UPDATE keys SET total_executions = total_executions + 1 WHERE key = ?', (key,))
        conn.commit()
        conn.close()
        
        return jsonify({
            'code': 'KEY_VALID',
            'message': 'Key hợp lệ',
            'data': {
                'total_executions': key_data[4] + 1,
                'note': key_data[5] or ''
            }
        })
        
    except Exception as e:
        print(f"Error in check_key: {e}")
        return jsonify({
            'code': 'SERVER_ERROR',
            'message': str(e)
        }), 500

@app.route('/api/freeresethwid', methods=['POST'])
def free_reset_hwid():
    """Reset HWID miễn phí"""
    try:
        data = request.json
        hwid = data.get('hwid')
        key = data.get('key')
        
        print(f"[RESET] HWID: {hwid}, Key: {key}")
        
        if not hwid or not key:
            return jsonify({
                'code': 'INVALID_REQUEST',
                'message': 'Thiếu thông tin'
            }), 400
        
        conn = get_db()
        c = conn.cursor()
        
        c.execute('SELECT hwid FROM keys WHERE key = ?', (key,))
        result = c.fetchone()
        
        if not result:
            conn.close()
            return jsonify({
                'code': 'INVALID_KEY',
                'message': 'Key không hợp lệ'
            }), 400
        
        # Kiểm tra cooldown (24 giờ)
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
                    'message': f'Vui lòng đợi {hours}h {minutes}m'
                }), 400
        
        # Reset HWID
        c.execute('UPDATE keys SET hwid = ? WHERE key = ?', ('unknown', key))
        
        if reset_data:
            c.execute('UPDATE hwid_resets SET last_reset = ? WHERE hwid = ?', (int(time.time()), hwid))
        else:
            c.execute('INSERT INTO hwid_resets (hwid, last_reset) VALUES (?, ?)', (hwid, int(time.time())))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Reset HWID thành công'
        })
        
    except Exception as e:
        print(f"Error in reset: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/rehwidpremium', methods=['POST'])
def premium_reset_hwid():
    """Reset HWID premium (không cooldown)"""
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
                'message': 'Thiếu key'
            }), 400
        
        conn = get_db()
        c = conn.cursor()
        
        c.execute('UPDATE keys SET hwid = ? WHERE key = ?', ('unknown', key))
        
        if c.rowcount == 0:
            conn.close()
            return jsonify({
                'code': 'KEY_NOT_FOUND',
                'message': 'Key không tồn tại'
            }), 404
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Reset HWID premium thành công'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/resethwidbycode', methods=['POST'])
def reset_hwid_by_code():
    """Reset HWID bằng code"""
    try:
        data = request.json
        reset_code = data.get('code')
        key = data.get('key')
        
        if not reset_code or not key:
            return jsonify({
                'code': 'INVALID_REQUEST',
                'message': 'Thiếu thông tin'
            }), 400
        
        # Danh sách code hợp lệ
        valid_codes = ['RESET2024', 'HOHO2024', 'FREE2024']
        
        if reset_code not in valid_codes:
            return jsonify({
                'code': 'INVALID_CODE',
                'message': 'Code không hợp lệ'
            }), 400
        
        conn = get_db()
        c = conn.cursor()
        
        c.execute('UPDATE keys SET hwid = ? WHERE key = ?', ('unknown', key))
        
        if c.rowcount == 0:
            conn.close()
            return jsonify({
                'code': 'KEY_NOT_FOUND',
                'message': 'Key không tồn tại'
            }), 404
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Reset HWID bằng code thành công'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/list_keys', methods=['GET'])
def list_keys():
    """Liệt kê keys (admin)"""
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

@app.route('/api/delete_key', methods=['POST'])
def delete_key():
    """Xóa key (admin)"""
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
                'message': 'Thiếu key'
            }), 400
        
        conn = get_db()
        c = conn.cursor()
        c.execute('DELETE FROM keys WHERE key = ?', (key,))
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Xóa key thành công'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Thống kê (admin)"""
    try:
        auth = request.headers.get('Authorization')
        if auth != f'Bearer {ADMIN_KEY}':
            return jsonify({
                'code': 'UNAUTHORIZED',
                'message': 'Invalid admin key'
            }), 401
        
        conn = get_db()
        c = conn.cursor()
        
        c.execute('SELECT COUNT(*) FROM keys')
        total_keys = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) FROM keys WHERE hwid != "unknown"')
        used_keys = c.fetchone()[0]
        
        c.execute('SELECT SUM(total_executions) FROM keys')
        total_executions = c.fetchone()[0] or 0
        
        c.execute('SELECT COUNT(*) FROM keys WHERE expires_at < ?', (int(time.time()),))
        expired_keys = c.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'total_keys': total_keys,
            'used_keys': used_keys,
            'total_executions': total_executions,
            'expired_keys': expired_keys
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'name': 'KLINUX XP Key System API',
        'version': '1.0.0',
        'key_format': 'KLINUX-LUANORI-XXXXX',
        'endpoints': {
            '/api/getkey': 'GET - Lấy key miễn phí',
            '/api/check_key': 'POST - Kiểm tra key',
            '/api/generate_key': 'POST - Tạo key (admin)',
            '/api/generate_bulk_keys': 'POST - Tạo nhiều key (admin)',
            '/api/freeresethwid': 'POST - Reset HWID miễn phí',
            '/api/rehwidpremium': 'POST - Reset HWID premium',
            '/api/resethwidbycode': 'POST - Reset HWID bằng code',
            '/api/list_keys': 'GET - Liệt kê keys (admin)',
            '/api/delete_key': 'POST - Xóa key (admin)',
            '/api/stats': 'GET - Thống kê (admin)'
        }
    })

# Vercel handler
def handler(event, context):
    return app