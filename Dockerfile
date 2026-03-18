# 使用 Python 3.9 的 Alpine 镜像
FROM python:3.9-alpine

# 设置工作目录
WORKDIR /app

# 复制当前文件夹内容到容器
COPY . .

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 暴露端口
EXPOSE 8008

# 启动应用
CMD ["python3", "app.py"]