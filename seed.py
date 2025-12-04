from app import create_app, db
from app.models import Role, User, SystemSetting

app = create_app()

with app.app_context():
    # 创建角色
    admin_role = Role.query.filter_by(name='admin').first()
    if not admin_role:
        admin_role = Role(name='admin', description='系统管理员')
        db.session.add(admin_role)
        
    user_role = Role.query.filter_by(name='user').first()
    if not user_role:
        user_role = Role(name='user', description='普通用户')
        db.session.add(user_role)
        
    db.session.commit()
    
    # 创建管理员账号
    admin_user = User.query.filter_by(username='admin').first()
    if not admin_user:
        admin_user = User(username='admin', name='Admin', role=admin_role)
        admin_user.set_password('admin123')
        db.session.add(admin_user)
        print("Admin user created: admin / admin123")
        
    # 创建普通用户账号测试
    test_user = User.query.filter_by(username='test').first()
    if not test_user:
        test_user = User(username='test', name='Test User', role=user_role)
        test_user.set_password('123456')
        db.session.add(test_user)
        print("Test user created: test / 123456")

    # 初始化系统设置
    app_name = SystemSetting.query.filter_by(key='app_name').first()
    if not app_name:
        app_name = SystemSetting(key='app_name', value='政企智能舆情分析报告生成智能体应用系统', description='应用名称')
        db.session.add(app_name)
        
    db.session.commit()
    print("Database seeded successfully.")
