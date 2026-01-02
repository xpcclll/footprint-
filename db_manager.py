#!/usr/bin/env python3
# 数据库管理工具

import sqlite3
import sys

DATABASE = 'footprints.db'

def backup_database():
    """备份数据库"""
    import shutil
    import time
    
    backup_file = f"footprints_backup_{int(time.time())}.db"
    shutil.copy2(DATABASE, backup_file)
    print(f"数据库已备份到: {backup_file}")

def export_to_json():
    """导出数据到JSON文件"""
    import json
    
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM footprints WHERE is_deleted = 0 ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    
    data = []
    for row in rows:
        data.append(dict(row))
    
    with open('footprints_export.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"已导出 {len(data)} 条足迹到 footprints_export.json")

def show_stats():
    """显示统计信息"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # 总足迹数
    cursor.execute("SELECT COUNT(*) FROM footprints WHERE is_deleted = 0")
    total = cursor.fetchone()[0]
    
    # 有图片的足迹数
    cursor.execute("SELECT COUNT(*) FROM footprints WHERE image_url IS NOT NULL AND is_deleted = 0")
    with_images = cursor.fetchone()[0]
    
    # 最近7天发布数
    cursor.execute("""
    SELECT COUNT(*) FROM footprints 
    WHERE timestamp >= datetime('now', '-7 days') 
    AND is_deleted = 0
    """)
    last_7_days = cursor.fetchone()[0]
    
    print(f"总足迹数: {total}")
    print(f"有图片的足迹: {with_images}")
    print(f"图片比例: {with_images/total*100:.1f}%")
    print(f"最近7天发布数: {last_7_days}")
    
    # 显示最新5条
    print("\n最新5条足迹:")
    cursor.execute("""
    SELECT id, username, substr(content, 1, 50) as preview, timestamp 
    FROM footprints 
    WHERE is_deleted = 0 
    ORDER BY timestamp DESC 
    LIMIT 5
    """)
    
    for row in cursor.fetchall():
        print(f"ID: {row[0]}, 用户: {row[1]}, 内容: {row[2]}..., 时间: {row[3]}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python3 db_manager.py [命令]")
        print("命令:")
        print("  backup    - 备份数据库")
        print("  export    - 导出数据到JSON")
        print("  stats     - 显示统计信息")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'backup':
        backup_database()
    elif command == 'export':
        export_to_json()
    elif command == 'stats':
        show_stats()
    else:
        print(f"未知命令: {command}")