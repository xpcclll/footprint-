#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sqlite3
import json
import uuid
import base64
import time
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory, g
from flask_cors import CORS
import hashlib

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 配置文件
DATABASE = 'footprints.db'
UPLOAD_FOLDER = 'uploads'
MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# 确保上传目录存在
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def get_db():
    """获取数据库连接"""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row  # 返回字典格式
    return db

def init_db():
    """初始化数据库"""
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        
        # 创建足迹表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS footprints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            content TEXT,
            image_url TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT,
            user_agent TEXT,
            is_deleted INTEGER DEFAULT 0
        )
        ''')
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON footprints(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_deleted ON footprints(is_deleted)')
        
        db.commit()
        
        print("数据库初始化完成")

@app.teardown_appcontext
def close_connection(exception):
    """关闭数据库连接"""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def save_image(base64_data):
    """保存Base64格式的图片到文件系统"""
    try:
        # 检查是否为Base64数据
        if not base64_data or not base64_data.startswith('data:image/'):
            return None
            
        # 提取Base64数据部分
        header, data = base64_data.split(',', 1)
        
        # 从header中获取文件扩展名
        if 'png' in header:
            ext = 'png'
        elif 'jpeg' in header or 'jpg' in header:
            ext = 'jpg'
        elif 'gif' in header:
            ext = 'gif'
        else:
            ext = 'png'
        
        # 生成唯一文件名
        filename = f"{int(time.time())}_{uuid.uuid4().hex[:8]}.{ext}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # 保存文件
        with open(filepath, 'wb') as f:
            f.write(base64.b64decode(data))
        
        return f'/uploads/{filename}'
        
    except Exception as e:
        print(f"保存图片失败: {e}")
        return None

@app.route('/')
def index():
    """返回前端页面"""
    return send_from_directory('.', '1.html')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """提供上传的图片文件"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/footprints', methods=['GET'])
def get_footprints():
    """获取足迹列表"""
    try:
        # 获取分页参数
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        offset = (page - 1) * page_size
        
        db = get_db()
        cursor = db.cursor()
        
        # 获取总数量
        cursor.execute('SELECT COUNT(*) as total FROM footprints WHERE is_deleted = 0')
        total = cursor.fetchone()['total']
        
        # 获取足迹数据（按时间倒序）
        cursor.execute('''
        SELECT id, username, content, image_url, timestamp 
        FROM footprints 
        WHERE is_deleted = 0 
        ORDER BY timestamp DESC 
        LIMIT ? OFFSET ?
        ''', (page_size, offset))
        
        footprints = []
        for row in cursor.fetchall():
            footprint = {
                'id': row['id'],
                'userName': row['username'],
                'content': row['content'],
                'imageUrl': row['image_url'],
                'timestamp': row['timestamp']
            }
            footprints.append(footprint)
        
        return jsonify({
            'success': True,
            'data': footprints,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total': total,
                'total_pages': (total + page_size - 1) // page_size
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取足迹失败: {str(e)}'
        }), 500

@app.route('/api/footprints', methods=['POST'])
def create_footprint():
    """创建新足迹"""
    try:
        data = request.json
        
        # 验证必填字段
        if not data.get('userName'):
            return jsonify({
                'success': False,
                'message': '用户名不能为空'
            }), 400
        
        # 检查内容和图片是否至少有一个
        if not data.get('content') and not data.get('imageData'):
            return jsonify({
                'success': False,
                'message': '至少需要填写内容或上传图片'
            }), 400
        
        db = get_db()
        cursor = db.cursor()
        
        # 处理图片
        image_url = None
        if data.get('imageData'):
            image_url = save_image(data['imageData'])
        
        # 获取客户端信息
        ip_address = request.remote_addr
        user_agent = request.headers.get('User-Agent', '')
        
        # 插入数据库
        cursor.execute('''
        INSERT INTO footprints (username, content, image_url, ip_address, user_agent)
        VALUES (?, ?, ?, ?, ?)
        ''', (data['userName'], data.get('content'), image_url, ip_address, user_agent))
        
        db.commit()
        
        # 返回创建的数据
        new_id = cursor.lastrowid
        cursor.execute('SELECT * FROM footprints WHERE id = ?', (new_id,))
        row = cursor.fetchone()
        
        return jsonify({
            'success': True,
            'message': '足迹发布成功',
            'data': {
                'id': row['id'],
                'userName': row['username'],
                'content': row['content'],
                'imageUrl': row['image_url'],
                'timestamp': row['timestamp']
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'发布足迹失败: {str(e)}'
        }), 500

@app.route('/api/footprints/<int:footprint_id>', methods=['DELETE'])
def delete_footprint(footprint_id):
    """软删除足迹"""
    try:
        db = get_db()
        cursor = db.cursor()
        
        # 标记为已删除
        cursor.execute('UPDATE footprints SET is_deleted = 1 WHERE id = ?', (footprint_id,))
        db.commit()
        
        return jsonify({
            'success': True,
            'message': '足迹删除成功'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'删除足迹失败: {str(e)}'
        }), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """获取统计信息"""
    try:
        db = get_db()
        cursor = db.cursor()
        
        # 获取足迹总数
        cursor.execute('SELECT COUNT(*) as total FROM footprints WHERE is_deleted = 0')
        total = cursor.fetchone()['total']
        
        # 获取有图片的足迹数量
        cursor.execute('SELECT COUNT(*) as with_image FROM footprints WHERE image_url IS NOT NULL AND is_deleted = 0')
        with_image = cursor.fetchone()['with_image']
        
        # 获取今天的足迹数量
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('SELECT COUNT(*) as today_count FROM footprints WHERE DATE(timestamp) = ? AND is_deleted = 0', (today,))
        today_count = cursor.fetchone()['today_count']
        
        # 获取最近活跃用户
        cursor.execute('''
        SELECT username, COUNT(*) as count 
        FROM footprints 
        WHERE is_deleted = 0 
        GROUP BY username 
        ORDER BY count DESC 
        LIMIT 5
        ''')
        top_users = [{'username': row['username'], 'count': row['count']} for row in cursor.fetchall()]
        
        return jsonify({
            'success': True,
            'data': {
                'total_footprints': total,
                'with_images': with_image,
                'today_count': today_count,
                'top_users': top_users
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取统计失败: {str(e)}'
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'footprints-backend'
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'message': '请求的资源不存在'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'message': '服务器内部错误'
    }), 500

if __name__ == '__main__':
    # 初始化数据库
    init_db()
    
    # 启动服务器
    print("足迹系统后端启动中...")
    print(f"访问地址: http://localhost:5000")
    print(f"API地址: http://localhost:5000/api/footprints")
    
    app.run(host='0.0.0.0', port=5000, debug=True)