# Android Phone Controller

一个基于 Python 的 Android 手机群控系统，支持多设备同时管理和实时屏幕监控。

## 功能特性

- 🔌 多设备同时连接管理
- 📱 实时屏幕截图显示
- 🎮 远程设备控制（音量、亮度等）
- 📊 可视化操作界面
- 🔄 自动截图刷新
- 💬 自定义命令发送

## 系统要求

- Python 3.8+
- Windows/Linux/macOS
- Android 设备需要配套的客户端应用

## 安装

1. 克隆仓库
```bash
git clone https://github.com/Read-Land/PhoneController.git
cd PhoneController
```

2. 创建虚拟环境
```bash
python -m venv .venv
```

3. 激活虚拟环境
```bash
# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate
```

4. 安装依赖
```bash
pip install -r requirements.txt
```

## 使用方法

1. 启动服务器
```bash
python final.py
```

2. 在界面中点击"启动服务器"按钮

3. 确保 Android 设备与电脑在同一网络下，连接到服务器

4. 使用控制面板管理设备

## 界面说明

- **左侧控制区**：设备控制按钮、命令输入、服务器管理
- **右上日志区**：显示操作日志和设备状态
- **右下屏幕区**：实时显示所有连接设备的屏幕

## 支持的命令

- `stream_start` - 开始屏幕流
- `stream_stop` - 停止屏幕流
- `volume_up` - 音量增加
- `volume_down` - 音量减少
- `brightness_up` - 亮度增加
- `brightness_down` - 亮度减少
- `screenshot` - 获取截图

## 项目结构

```
PhoneControl/
├── final.py              # 主程序
├── requirements.txt      # 依赖列表
├── screenshots/          # 截图保存目录
└── platform-tools/       # Android 工具
```

## 技术栈

- **GUI**: Tkinter
- **网络**: Socket (TCP)
- **图像处理**: Pillow
- **多线程**: Threading

## 注意事项

- 默认监听端口：8888
- 确保防火墙允许该端口通信
- Android客户端需要特定的应用程序

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

## 联系方式

如有问题或建议，请通过 GitHub Issues 联系。
