# Power Bank (Django + MySQL)

这是一个基于 Django 的 Web 应用基础框架，包含：

- 前端页面（Django Template）
- 后端 API（Django REST Framework）
- MySQL 数据库配置（通过环境变量）

## 项目结构

```text
.
├── api/                  # 后端 API 应用
├── config/               # Django 项目配置
├── static/               # 静态资源
├── templates/            # 前端模板
├── web/                  # 前端页面应用
├── manage.py
├── pyproject.toml
└── .env.example
```

## 快速开始

1. 安装依赖

```bash
uv sync
```

2. 配置环境变量

```bash
cp .env.example .env
```

3. 确保本地 MySQL 已创建数据库（默认名：`power_bank`）

4. 执行迁移

```bash
# 生成迁移
uv run python manage.py makemigrations

uv run python manage.py migrate
```

5. 启动服务

```bash
uv run python manage.py runserver
```

## 访问地址

- 前端页面: `http://127.0.0.1:8000/`
- API 健康检查: `http://127.0.0.1:8000/api/health/`


## 提取可翻译的字符串

```bash
django-admin makemessages -all
```

## 翻译字符串
```bash
django-admin compilemessages
```
