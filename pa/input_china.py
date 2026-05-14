import json
import os

from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from datetime import date, datetime
import pymysql

pymysql.install_as_MySQLdb()
app = Flask(__name__)

# 数据库连接配置（替换为你的密码）
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:1111@localhost:3306/rain'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JSON_AS_ASCII'] = False
db = SQLAlchemy(app)


# -------------------------- 模型定义（手动指定 ID） --------------------------
# 1. 省份表模型（ID 手动指定）
class Province(db.Model):
    __tablename__ = 'province'
    id = db.Column(db.Integer, primary_key=True)  # 去掉 autoincrement=True
    name = db.Column(db.String(50), nullable=False, unique=True)
    cities = db.relationship('City', backref='province', lazy=True)


# 2. 城市表模型（ID 手动指定）
class City(db.Model):
    __tablename__ = 'city'
    id = db.Column(db.Integer, primary_key=True)  # 去掉 autoincrement=True
    name = db.Column(db.String(50), nullable=False)
    province_id = db.Column(db.Integer, db.ForeignKey('province.id'), nullable=False)
    rainfall_records = db.relationship('CityDailyRainfall', backref='city', lazy=True)


# 3. 城市日降雨量表（ID 保留自增，流水数据无需手动指定）
class CityDailyRainfall(db.Model):
    __tablename__ = 'city_daily_rainfall'
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    city_id = db.Column(db.Integer, db.ForeignKey('city.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    rainfall = db.Column(db.Numeric(5, 1), nullable=False)
    source = db.Column(db.String(50))
    created_at = db.Column(db.TIMESTAMP, default=datetime.now)


# -------------------------- 接口修改（支持手动指定 ID） --------------------------
# 1. 新增省份（手动指定 ID）
@app.route('/province/add', methods=['GET'])
def add_province_get():
    # 从URL参数获取id和name（如 http://127.0.0.1:5000/province/add?id=10133&name=香港）
    province_id = request.args.get('id')
    province_name = request.args.get('name')

    # 校验参数
    if not province_id or not province_name:
        return jsonify({'error': '请传参：id（数字）、name（省份名）'}), 400
    try:
        province_id = int(province_id)
    except ValueError:
        return jsonify({'error': 'id必须是数字'}), 400

    # 复用原有校验逻辑
    if Province.query.get(province_id):
        return jsonify({'error': f'省份ID {province_id} 已存在'}), 400
    if Province.query.filter_by(name=province_name).first():
        return jsonify({'error': f'省份名称 {province_name} 已存在'}), 400

    # 新增省份
    new_province = Province(id=province_id, name=province_name)
    db.session.add(new_province)
    db.session.commit()
    return jsonify({'msg': '省份添加成功', 'province': {'id': province_id, 'name': province_name}}), 201


# 2. 新增城市（手动指定 ID）
@app.route('/city', methods=['POST'])
def add_city():
    data = request.json
    # 校验必填字段：id + name + province_id
    required_fields = ['id', 'name', 'province_id']
    if not data or not all(field in data for field in required_fields):
        return jsonify({'error': '城市ID、名称和省份ID不能为空'}), 400

    # 校验 ID 格式
    if not isinstance(data['id'], int) or data['id'] <= 0:
        return jsonify({'error': '城市ID必须是正整数'}), 400

    # 校验省份是否存在
    province = Province.query.get(data['province_id'])
    if not province:
        return jsonify({'error': f'省份ID {data["province_id"]} 不存在'}), 400

    # 校验城市 ID 是否已存在
    existing_city_id = City.query.get(data['id'])
    if existing_city_id:
        return jsonify({'error': f'城市ID {data["id"]} 已存在'}), 400

    # 校验同一省份下城市名称是否重复
    existing_city_name = City.query.filter_by(
        name=data['name'],
        province_id=data['province_id']
    ).first()
    if existing_city_name:
        return jsonify({'error': f'省份ID {data["province_id"]} 下已存在城市 {data["name"]}'}), 400

    # 创建新城市（手动指定 ID）
    new_city = City(id=data['id'], name=data['name'], province_id=data['province_id'])
    db.session.add(new_city)
    db.session.commit()
    return jsonify({
        'msg': '城市添加成功',
        'city': {'id': new_city.id, 'name': new_city.name, 'province_id': new_city.province_id}
    }), 201


# 3. 根路径测试
@app.route('/', methods=['GET'])
def index():
    return jsonify({
        'msg': '服务运行正常，支持手动指定省份/城市ID',
        'available_api': {
            '新增省份': 'POST /province',
            '新增城市': 'POST /city',
        },
        '新增省份示例（POST /province）': {
            'id': 1001,
            'name': '广东省'
        },
        '新增城市示例（POST /city）': {
            'id': 2001,
            'name': '广州市',
            'province_id': 1001
        }
    }), 200

@app.route('/province/batch_import', methods=['GET'])
def batch_import_provinces():
    # 1. 读取provinces.txt文件（请替换为你的txt文件实际路径，比如F:/test/provinces.txt）
    txt_path = "provinces.txt"  # 若txt和py文件同目录，直接写文件名；否则写绝对路径
    if not os.path.exists(txt_path):
        return jsonify({'error': f'文件不存在，路径：{txt_path}'}), 404

    # 2. 读取并解析JSON数据
    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            province_list = json.load(f)
    except json.JSONDecodeError:
        return jsonify({'error': '文件JSON格式错误，请检查语法（如逗号、冒号）'}), 400
    except Exception as e:
        return jsonify({'error': f'读取文件失败：{str(e)}'}), 500

    # 3. 批量处理导入（跳过已存在、格式错误的，记录导入结果）
    success = []  # 导入成功的省份
    skip = []     # 跳过的省份（已存在）
    error = []    # 导入失败的省份（格式错误）

    for item in province_list:
        # 校验字段是否完整
        if not item.get('id') or not item.get('name'):
            error.append({'data': item, 'reason': '缺少id或name字段'})
            continue

        # 转换id为整数（txt里是字符串，数据库是int）
        try:
            province_id = int(item['id'])
            province_name = item['name'].strip()  # 去除首尾空格
        except ValueError:
            error.append({'data': item, 'reason': 'id不是有效数字'})
            continue

        # 校验是否已存在
        if Province.query.get(province_id) or Province.query.filter_by(name=province_name).first():
            skip.append({'id': province_id, 'name': province_name, 'reason': 'ID或名称已存在'})
            continue

        # 4. 插入数据库
        new_province = Province(id=province_id, name=province_name)
        db.session.add(new_province)
        success.append({'id': province_id, 'name': province_name})

    # 5. 提交事务（批量提交，提升效率）
    if success:
        db.session.commit()
    # 失败则回滚（避免部分数据导入）
    elif error:
        db.session.rollback()

    # 6. 返回导入结果
    return jsonify({
        'msg': '批量导入完成',
        '统计': {
            '成功导入': len(success),
            '跳过（已存在）': len(skip),
            '导入失败（格式错误）': len(error)
        },
        '成功列表': success,
        '跳过列表': skip,
        '失败列表': error
    }), 200

@app.route('/city/batch_import', methods=['GET'])
def batch_import_cities():
    # 1. 读取citys.txt文件（替换为你的txt文件实际路径，如F:/test/citys.txt）
    txt_path = "citys_fixed.txt"  # 若txt和py文件同目录，直接写文件名；否则写绝对路径
    if not os.path.exists(txt_path):
        return jsonify({'error': f'文件不存在，路径：{txt_path}'}), 404

    # 2. 读取并解析JSON数据
    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            city_list = json.load(f)
    except json.JSONDecodeError:
        return jsonify({'error': '文件JSON格式错误，请用在线工具校验'}), 400
    except Exception as e:
        return jsonify({'error': f'读取文件失败：{str(e)}'}), 500

    # 3. 批量处理导入（跳过无效数据，记录结果）
    success = []  # 导入成功
    skip = []     # 跳过（已存在/关联省份不存在）
    error = []    # 导入失败（格式错误）

    for item in city_list:
        # 校验必填字段（id、name、province_id）
        required_fields = ['id', 'name', 'province_id']
        if not all(field in item for field in required_fields):
            error.append({'data': item, 'reason': '缺少id、name或province_id字段'})
            continue

        # 转换字段类型（txt中是字符串，数据库是int）
        try:
            city_id = int(item['id'])
            province_id = int(item['province_id'])
            city_name = item['name'].strip()  # 去除首尾空格
        except ValueError:
            error.append({'data': item, 'reason': 'id或province_id不是有效数字'})
            continue

        # 校验关联的省份是否存在
        province = Province.query.get(province_id)
        if not province:
            skip.append({'data': item, 'reason': f'关联的省份ID {province_id} 不存在'})
            continue

        # 校验城市ID是否已存在
        if City.query.get(city_id):
            skip.append({'data': item, 'reason': f'城市ID {city_id} 已存在'})
            continue

        # 校验同一省份下城市名称是否重复
        if City.query.filter_by(name=city_name, province_id=province_id).first():
            skip.append({'data': item, 'reason': f'省份{province_id}下已存在城市{city_name}'})
            continue

        # 4. 插入数据库
        new_city = City(id=city_id, name=city_name, province_id=province_id)
        db.session.add(new_city)
        success.append({'id': city_id, 'name': city_name, 'province_id': province_id})

    # 5. 批量提交事务（提升效率）
    if success:
        db.session.commit()
    elif error:
        db.session.rollback()

    # 6. 返回导入结果
    return jsonify({
        'msg': '城市批量导入完成',
        '统计': {
            '成功导入': len(success),
            '跳过': len(skip),
            '导入失败': len(error)
        },
        '成功列表（前10条）': success[:10],  # 只显示前10条，避免返回数据过大
        '跳过列表（前10条）': skip[:10],
        '失败列表': error
    }), 200


# 启动服务
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # 仅创建不存在的表，不影响已有数据
    app.run(debug=True)
