import socket
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
import threading
import os
import time
from datetime import datetime
from PIL import Image, ImageTk
import queue


class AndroidPhoneController:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.root = tk.Tk()
        self.root.title("智能手机群控中心")
        self.root.geometry("1400x800")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)  # 关闭事件处理

        self.server_socket = None
        self.command_input = tk.StringVar()
        self.clients = {}  # {client_id: (socket, address, last_active)}
        self.running = False
        self.client_lock = threading.Lock()
        self.screen_widgets_lock = threading.Lock()
        self.screen_widgets = {}  # {client_id: (frame, label, img_obj)}
        self.grid_size = (2, 3)  # 默认2行3列布局
        self.screen_width = 300  # 每个屏幕显示宽度
        self.screen_height = 500  # 每个屏幕显示高度

        # 定时刷新截图配置
        self.auto_refresh_interval = 5  # 定时刷新间隔（秒）
        self.auto_refresh_running = False  # 定时刷新开关

        # 截图更新队列（解决线程同步问题）
        self.screenshot_queue = queue.Queue()

        # 初始化UI
        self.setup_ui()

        # 启动队列处理
        self.process_screenshot_queue()

        self.timeout = 60

    def setup_ui(self):
        """创建完整的UI界面"""
        # 主框架使用PanedWindow实现可调整区域
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        main_paned.pack_propagate(False)

        # 左侧控制区域
        left_frame = ttk.Frame(main_paned, width=200)
        main_paned.add(left_frame, weight=0)

        # 控制按钮区域
        control_frame = ttk.LabelFrame(left_frame, text="设备控制")
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        # 控制按钮列表
        control_buttons = [
            "stream_start", "stream_stop",
            "volume_up", "volume_down",
            "brightness_up", "brightness_down",
        ]
        for i, text in enumerate(control_buttons):
            row = i // 2
            col = i % 2
            btn = ttk.Button(control_frame, text=text, command=lambda t=text: self.send_command(t))
            btn.grid(row=row, column=col, padx=2, pady=2, sticky="ew")


        # 命令输入区域
        cmd_frame = ttk.LabelFrame(left_frame, text="自定义命令")
        cmd_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(cmd_frame, text="命令:").pack(anchor=tk.W, padx=2, pady=2)
        self.command_entry = ttk.Entry(cmd_frame, textvariable=self.command_input)
        self.command_entry.pack(fill=tk.X, padx=2, pady=2)
        self.command_entry.bind("<Return>", lambda event: self.send_custom_command())

        cmd_btn_frame = ttk.Frame(cmd_frame)
        cmd_btn_frame.pack(fill=tk.X, padx=2, pady=2)
        ttk.Button(cmd_btn_frame, text="发送给所有",
                   command=self.send_custom_command).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        ttk.Button(cmd_btn_frame, text="发送给选中",
                   command=self.send_to_selected).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)

        # 服务器控制
        server_frame = ttk.LabelFrame(left_frame, text="服务器控制")
        server_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(server_frame, text="启动服务器",
                   command=self.start_server_thread).pack(fill=tk.X, padx=2, pady=2)
        ttk.Button(server_frame, text="关闭服务器",
                   command=self.close_server).pack(fill=tk.X, padx=2, pady=2)

        # 客户端列表
        client_frame = ttk.LabelFrame(left_frame, text="已连接设备")
        client_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 添加滚动条
        client_scroll = ttk.Scrollbar(client_frame)
        client_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.client_listbox = tk.Listbox(client_frame, yscrollcommand=client_scroll.set)
        self.client_listbox.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        client_scroll.config(command=self.client_listbox.yview)
        self.client_listbox.bind('<<ListboxSelect>>', self.on_client_select)

        # 右侧显示区域
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=1)

        # 日志区域
        log_frame = ttk.LabelFrame(right_frame, text="操作日志")
        log_frame.pack(fill=tk.X, padx=5, pady=5)

        # 日志滚动条
        log_scroll = ttk.Scrollbar(log_frame)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=8,
                                                  yscrollcommand=log_scroll.set)
        self.log_text.pack(fill=tk.X, padx=2, pady=2)
        log_scroll.config(command=self.log_text.yview)
        self.log_text.config(state=tk.DISABLED)

        # 屏幕显示区域
        screen_container = ttk.LabelFrame(right_frame, text="设备屏幕")
        screen_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 创建带滚动条的画布
        canvas = tk.Canvas(screen_container)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(screen_container, orient="vertical", command=canvas.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        self.screen_frame = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=self.screen_frame, anchor="nw")

        # 添加鼠标滚轮支持
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))

        # 初始日志
        self.log("程序已启动，等待服务器启动...")

    def on_client_select(self, event):
        """处理客户端选择事件"""
        selected = self.client_listbox.curselection()
        if selected:
            client_id = selected[0] + 1
            self.log(f"已选择客户端: {client_id}")

    def send_command(self, command):
        """发送预设命令"""
        send_cmd = command

        with self.client_lock:
            clients_copy = list(self.clients.items())

        if not clients_copy:
            messagebox.showwarning("提示", "无连接的设备")
            return

        success = False
        for cid, (sock, _, _) in clients_copy:
            try:
                sock.sendall(send_cmd.encode('utf-8') + b'\n')
                self.log(f"已向设备 {cid} 发送命令：{command}")
            except Exception as e:
                self.log(f"发送给设备 {cid} 失败：{e}")

    def toggle_auto_refresh(self):
        """切换定时刷新截图功能"""
        self.auto_refresh_running = not self.auto_refresh_running
        if self.auto_refresh_running:
            self.log(f"定时刷新截图已开启（间隔：{self.auto_refresh_interval} 秒）")
            self._auto_refresh_loop()
            messagebox.showinfo("成功", "定时刷新截图已开启")
        else:
            self.log("定时刷新截图已关闭")
            messagebox.showinfo("成功", "定时刷新截图已关闭")

    def _auto_refresh_loop(self):
        """定时刷新截图循环"""
        if not self.auto_refresh_running:
            return
        self.send_command("获取所有截图")
        self.root.after(self.auto_refresh_interval * 1000, self._auto_refresh_loop)

    def send_custom_command(self):
        """发送自定义命令"""
        command = self.command_input.get().strip()
        if not command:
            messagebox.showwarning("提示", "请输入命令")
            return

        with self.client_lock:
            clients_copy = list(self.clients.items())

        if not clients_copy:
            messagebox.showwarning("提示", "无连接的设备")
            return

        success = False
        for cid, (sock, _, _) in clients_copy:
            try:
                sock.sendall(command.encode('utf-8') + b'\n')
                self.log(f"已向设备 {cid} 发送命令：{command}")
                success = True
            except Exception as e:
                self.log(f"发送给设备 {cid} 失败：{e}")

        if success:
            self.command_input.set("")
            messagebox.showinfo("成功", "命令已发送")

    def send_to_selected(self):
        """发送命令给选中的客户端"""
        selected = self.client_listbox.curselection()
        if not selected:
            messagebox.showwarning("提示", "请选择设备")
            return

        cid = selected[0] + 1
        command = self.command_input.get().strip()
        if not command:
            messagebox.showwarning("提示", "请输入命令")
            return

        with self.client_lock:
            if cid not in self.clients:
                messagebox.showwarning("提示", "设备已断开")
                return
            sock, _, _ = self.clients[cid]

        try:
            sock.sendall(command.encode('utf-8') + b'\n')
            self.log(f"已向设备 {cid} 发送命令：{command}")
            self.command_input.set("")
            messagebox.showinfo("成功", f"命令已发送到设备 {cid}")
        except Exception as e:
            self.log(f"发送失败：{e}")
            messagebox.showerror("失败", f"发送失败：{e}")

    def log(self, message):
        """添加日志信息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def start_server_thread(self):
        """启动服务器线程"""
        if not self.running:
            thread = threading.Thread(target=self.start_server, args=(self.host, self.port))
            thread.daemon = True
            thread.start()
            self.running = True
            self.log("正在启动服务器...")

    def start_server(self, host, port):
        """启动TCP服务器"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((host, port))
            self.server_socket.listen(10)
            self.server_socket.settimeout(1.0)
            self.running = True
            self.log(f"服务器启动成功，监听 {host}:{port}")
            self.accept_connections()
        except Exception as e:
            self.log(f"服务器启动失败：{e}")
            self.root.after(0, lambda: messagebox.showerror("错误", f"启动失败：{e}"))
            self.running = False

    def accept_connections(self):
        """接收客户端连接"""
        while self.running and self.server_socket:
            try:
                sock, addr = self.server_socket.accept()
                sock.settimeout(30.0)
                with self.client_lock:
                    client_id = len(self.clients) + 1
                    self.clients[client_id] = (sock, addr, time.time())

                self.root.after(0, self.add_screen_widget, client_id)
                self.root.after(0, self.update_client_listbox)

                self.log(f"新设备连接：ID {client_id}，地址 {addr}")

                self.root.after(2000, lambda c=client_id: self.send_single_command(c, "screenshot"))

                client_thread = threading.Thread(target=self.handle_client, args=(client_id,))
                client_thread.daemon = True
                client_thread.start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    self.log(f"连接接受错误：{e}")

    def update_client_listbox(self):
        """更新客户端列表"""
        with self.client_lock:
            self.client_listbox.delete(0, tk.END)
            for idx, (sock, addr, _) in enumerate(self.clients.values()):
                self.client_listbox.insert(tk.END, f"设备 {idx + 1}: {addr}")

    def add_screen_widget(self, client_id):
        """添加新的屏幕显示组件"""
        with self.screen_widgets_lock:
            if client_id in self.screen_widgets:
                return

        with self.screen_widgets_lock:
            clients_count = len(self.screen_widgets)

        row = clients_count // self.grid_size[1]
        col = clients_count % self.grid_size[1]

        frame = ttk.LabelFrame(self.screen_frame, text=f"设备 {client_id}")
        frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")

        screen_label = ttk.Label(frame, text="等待屏幕数据...")
        screen_label.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        with self.screen_widgets_lock:
            self.screen_widgets[client_id] = (frame, screen_label, None)

        self.log(f"设备 {client_id} 显示组件已创建")

    def send_single_command(self, client_id, command):
        """向单个设备发送命令"""
        with self.client_lock:
            if client_id not in self.clients:
                messagebox.showwarning("提示", "设备已断开")
                return
            sock, _, _ = self.clients[client_id]

        try:
            sock.sendall(command.encode('utf-8') + b'\n')
            self.log(f"已向设备 {client_id} 发送命令：{command}")
        except Exception as e:
            self.log(f"发送给设备 {client_id} 失败：{e}")

    def handle_client(self, client_id):
        """处理客户端通信"""
        try:
            with self.client_lock:
                if client_id not in self.clients:
                    return
                sock, addr, _ = self.clients[client_id]

            while self.running:
                with self.client_lock:
                    if client_id not in self.clients:
                        break
                    sock, addr, _ = self.clients[client_id]
                    self.clients[client_id] = (sock, addr, time.time())

                type_bytes = b''
                while len(type_bytes) < 4:
                    chunk = sock.recv(4 - len(type_bytes))
                    if not chunk:
                        raise Exception("连接已关闭")
                    type_bytes += chunk

                if type_bytes == b'\x00\x00\x00\x00':
                    len_bytes = b''
                    while len(len_bytes) < 4:
                        chunk = sock.recv(4 - len(len_bytes))
                        if not chunk:
                            raise Exception("连接已关闭")
                        len_bytes += chunk
                    text_len = int.from_bytes(len_bytes, byteorder='big')
                    text_data = b''
                    while len(text_data) < text_len:
                        chunk = sock.recv(min(1024, text_len - len(text_data)))
                        if not chunk:
                            raise Exception("连接已关闭")
                        text_data += chunk
                    self.log(f"设备 {client_id} 消息：{text_data.decode('utf-8')}")

                elif type_bytes == b'\x00\x00\x00\x01':
                    len_bytes = b''
                    while len(len_bytes) < 4:
                        chunk = sock.recv(4 - len(len_bytes))
                        if not chunk:
                            raise Exception("连接已关闭")
                        len_bytes += chunk
                    img_len = int.from_bytes(len_bytes, byteorder='big')
                    self.recv_and_save_screenshot(client_id, img_len, sock)

        except Exception as e:
            self.log(f"设备 {client_id} 连接断开：{e}")
            self.remove_client(client_id)

    def recv_and_save_screenshot(self, client_id, img_len, sock):
        """接收并保存截图"""
        try:
            img_data = b''
            while len(img_data) < img_len:
                chunk = sock.recv(min(4096, img_len - len(img_data)))
                if not chunk:
                    raise Exception(f"截图接收中断：已接收 {len(img_data)}/{img_len} 字节")
                img_data += chunk

            if not (img_data.startswith(b'\x89PNG') or img_data.startswith(b'\xff\xd8')):
                raise Exception("接收的不是有效图片数据（非PNG/JPG格式）")

            filepath = os.path.join("screenshots", f"client_{client_id}.png")
            os.makedirs("screenshots", exist_ok=True)
            with open(filepath, "wb") as f:
                f.write(img_data)

            self.screenshot_queue.put((filepath, client_id))

        except Exception as e:
            self.log(f"截图接收失败（设备 {client_id}）：{e}")

    def process_screenshot_queue(self):
        """处理截图更新队列"""
        try:
            while True:
                filepath, client_id = self.screenshot_queue.get_nowait()
                self._update_screenshot_internal(filepath, client_id)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.process_screenshot_queue)

    def _update_screenshot_internal(self, filepath, client_id):
        """内部截图更新方法"""
        with self.screen_widgets_lock:
            if client_id not in self.screen_widgets:
                if client_id in self.clients:
                    self.log(f"设备 {client_id} 组件不存在，尝试重新创建...")
                    self.add_screen_widget(client_id)
                else:
                    self.log(f"设备 {client_id} 未找到显示组件，无法更新截图")
                    return

            frame, label, old_img = self.screen_widgets[client_id]

        if not os.path.isfile(filepath):
            self.log(f"截图文件不存在：{filepath}")
            label.configure(text="截图文件丢失", image='')
            return

        try:
            img = Image.open(filepath)
            orig_w, orig_h = img.size
            target_w, target_h = self.screen_width, self.screen_height

            scale = min(target_w / orig_w, target_h / orig_h)
            new_w = int(orig_w * scale)
            new_h = int(orig_h * scale)

            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            img_tk = ImageTk.PhotoImage(img)

            label.config(image=img_tk, text='')
            label.image = img_tk

            with self.screen_widgets_lock:
                self.screen_widgets[client_id] = (frame, label, img_tk)

        except Exception as e:
            self.log(f"截图显示失败（设备 {client_id}）：{e}")
            label.configure(text=f"显示失败：{str(e)[:20]}", image='')

    def remove_client(self, client_id):
        """移除客户端并清理界面"""
        with self.client_lock:
            if client_id not in self.clients:
                return
            sock, addr, _ = self.clients.pop(client_id)

        try:
            sock.close()
        except:
            pass

        with self.screen_widgets_lock:
            if client_id in self.screen_widgets:
                frame, _, _ = self.screen_widgets.pop(client_id)
                frame.destroy()
                self.log(f"设备 {client_id} 屏幕已移除")

        self.root.after(0, self.rearrange_screens)
        self.root.after(0, self.update_client_listbox)

        self.log(f"设备 {client_id} 已断开，当前在线：{len(self.clients)}")

    def rearrange_screens(self):
        """重新排列剩余设备的显示位置"""
        with self.screen_widgets_lock:
            widgets = list(self.screen_widgets.items())
            for client_id, (frame, label, img) in widgets:
                frame.grid_forget()

        for idx, (client_id, (frame, label, img)) in enumerate(widgets):
            row = idx // self.grid_size[1]
            col = idx % self.grid_size[1]
            frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")

    def close_server(self):
        """关闭服务器"""
        if self.running and self.server_socket:
            self.auto_refresh_running = False
            self.running = False
            try:
                self.server_socket.close()
            except:
                pass

            with self.client_lock:
                for sock, _, _ in self.clients.values():
                    try:
                        sock.close()
                    except:
                        pass
                self.clients.clear()

            with self.screen_widgets_lock:
                for client_id in list(self.screen_widgets.keys()):
                    frame, _, _ = self.screen_widgets.pop(client_id)
                    frame.destroy()

            self.log("服务器已关闭")
            self.update_client_listbox()
        else:
            messagebox.showwarning("提示", "无运行中的服务器")

    def on_closing(self):
        """窗口关闭事件处理"""
        if messagebox.askokcancel("退出", "确定要退出程序吗？"):
            self.close_server()
            self.root.destroy()

    def run(self):
        """运行主程序"""
        self.root.mainloop()


if __name__ == "__main__":
    name = socket.gethostbyname(socket.gethostname())
    app = AndroidPhoneController(host=name, port=8888)
    app.run()