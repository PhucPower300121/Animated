import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
from _module1 import save_gif_frames
import os
from tkinterdnd2 import DND_FILES, TkinterDnD
import threading
import time
import queue
import sys

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


class GIFViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Animated v1.0.0")
        self.root.geometry("800x600")
        self.root.iconbitmap(resource_path("icon.ico"))
        
        # Variables
        self.gif_path = None
        self.gif_frames = []
        self.source_frames = []  # Frame gốc RGBA để lưu transparent GIF
        self.current_frame = 0
        self.is_playing = True
        self.animation_id = None
        self.zoom_level = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self.is_dragging = False
        self.display_image = None
        self.speed_level = 1.0  # 0.5x to 2.0x
        self.is_scrubbing = False
        self.is_looping = True  # Loop GIF by default
        self.frame_durations = []  # Lưu duration của từng frame
        self.resized_frame_cache = {}  # Cache frame đã resize để tối ưu
        
        # Timing và threading
        self.start_time = None
        self.total_duration = 0.0  # Tổng duration (ms) từ frame 0 đến hiện tại
        self.render_queue = queue.Queue(maxsize=1)
        self.resize_thread = None
        self.stop_resize_thread = False
        self.is_updating_frame = False  # Prevent concurrent frame updates
        self.zoom_pan_timer = None  # Debounce timer for zoom/pan
        self.pending_animation_id = None  # Track scheduled animation callbacks
        
        # Undo/Redo history
        self.history_stack = []  # Lưu trạng thái GIF
        self.history_index = -1  # Index hiện tại trong history
        self.saved_history_index = -1  # Index lúc cuối cùng được lưu
        
        # Create UI
        self.create_menu()
        self.create_canvas()
        self.create_controls()
        self.setup_drag_drop()
        self.setup_keyboard()
        
    def setup_drag_drop(self):
        """Thiết lập kéo thả file"""
        self.canvas.drop_target_register(DND_FILES)
        self.canvas.dnd_bind('<<Drop>>', self.on_drop_file)
    
    def setup_keyboard(self):
        """Thiết lập keyboard shortcuts"""
        self.root.bind("<space>", self.on_space_key)
        self.root.bind("<Left>", self.on_left_arrow)
        self.root.bind("<Right>", self.on_right_arrow)
        self.root.bind("<Control-z>", lambda e: self.undo())
        self.root.bind("<Control-y>", lambda e: self.redo())
        self.root.bind("<Control-o>", lambda e: self.open_file())
        self.root.bind("<Control-s>", lambda e: self.save_file())
        self.root.bind("<Control-Shift-S>", lambda e: self.save_file_as())
    
    def start_resize_thread(self):
        """Start background thread để resize frame"""
        if self.resize_thread is not None and self.resize_thread.is_alive():
            return
        
        self.stop_resize_thread = False
        self.resize_thread = threading.Thread(target=self._resize_worker, daemon=True)
        self.resize_thread.start()
    
    def _resize_worker(self):
        """Worker thread để resize frame mà không chặn main thread"""
        while not self.stop_resize_thread:
            try:
                task = self.render_queue.get(timeout=0.1)
                if task is None:
                    break
                
                frame_idx, frame, new_width, new_height = task
                resample = Image.Resampling.LANCZOS if self.speed_level <= 1.5 else Image.Resampling.NEAREST
                frame_resized = frame.resize((new_width, new_height), resample)
                
                # Lưu vào cache
                cache_key = (frame_idx, new_width, new_height)
                self.resized_frame_cache[cache_key] = frame_resized
                
            except queue.Empty:
                continue
            except Exception:
                pass
    
    def stop_resize_thread(self):
        """Dừng background thread"""
        self.stop_resize_thread = True
        if self.resize_thread and self.resize_thread.is_alive():
            self.resize_thread.join(timeout=1)
    
    def on_drop_file(self, event):
        """Xử lý kéo thả file"""
        files = self.root.tk.splitlist(event.data)
        if files:
            # Lấy file đầu tiên
            file_path = files[0].strip('{}')
            if file_path.lower().endswith('.gif'):
                try:
                    self.gif_path = file_path
                    self.load_gif()
                    self.reset_view()
                    self.update_frame()
                except Exception as e:
                    messagebox.showerror("Lỗi", f"Không thể mở file: {str(e)}")
            else:
                messagebox.showwarning("Cảnh báo", "Vui lòng kéo thả file GIF!")
    
    def on_space_key(self, event):
        """Xử lý phím space"""
        if self.gif_frames:
            self.toggle_play_pause()
        return "break"
    
    def on_left_arrow(self, event):
        """Xử lý phím mũi tên trái"""
        if self.gif_frames and not self.is_playing:
            self.current_frame = (self.current_frame - 1) % len(self.gif_frames)
            self.start_time = None
            self.update_frame()
        return "break"
    
    def on_right_arrow(self, event):
        """Xử lý phím mũi tên phải"""
        if self.gif_frames and not self.is_playing:
            self.current_frame = (self.current_frame + 1) % len(self.gif_frames)
            self.start_time = None
            self.update_frame()
        return "break"

        
    def create_menu(self):
        """Tạo menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Mở file GIF", command=self.open_file, accelerator="Ctrl+O")
        file_menu.add_command(label="Lưu", command=self.save_file, accelerator="Ctrl+S")
        file_menu.add_command(label="Lưu thành...", command=self.save_file_as, accelerator="Ctrl+Shift+S")
        file_menu.add_separator()
        file_menu.add_command(label="Thông tin ảnh", command=self.show_image_info)
        file_menu.add_separator()
        file_menu.add_command(label="Thoát", command=self.on_closing, accelerator="Alt+F4")
        
        # View menu (rename từ Edit)
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Phóng to", command=self.zoom_in)
        view_menu.add_command(label="Thu nhỏ", command=self.zoom_out)
        view_menu.add_command(label="Fit to window", command=self.fit_to_window)
        view_menu.add_separator()
        view_menu.add_command(label="Reset", command=self.reset_view)
        
        # Edit menu (new - for editing GIF)
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Undo", command=self.undo, accelerator="Ctrl+Z")
        edit_menu.add_command(label="Redo", command=self.redo, accelerator="Ctrl+Y")
        edit_menu.add_separator()
        edit_menu.add_command(label="Crop", command=self.open_crop_dialog)
        edit_menu.add_command(label="Trim", command=self.open_trim_dialog)
        edit_menu.add_command(label="Resize", command=self.open_resize_dialog)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Hướng dẫn", command=self.show_help)
        help_menu.add_command(label="Về", command=self.show_about)
        
        # Setup close handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def show_image_info(self):
        """Hiển thị thông tin GIF"""
        if not self.gif_frames or not self.gif_path:
            messagebox.showwarning("Cảnh báo", "Chưa mở GIF!")
            return

        try:
            import os
            import subprocess
            import platform

            # File info
            file_name = os.path.basename(self.gif_path)
            folder_path = os.path.dirname(self.gif_path)

            # Size KB
            file_size = os.path.getsize(self.gif_path) / 1024

            # Resolution
            first_frame = self.gif_frames[0]
            width, height = first_frame.size

            # Mode / color format
            color_mode = self.source_frames[0].mode if self.source_frames else first_frame.mode

            # Frames
            total_frames = len(self.gif_frames)

            # Duration
            total_duration_ms = sum(self.frame_durations)
            total_duration_sec = total_duration_ms / 1000

            # Popup
            info_window = tk.Toplevel(self.root)
            info_window.title("Thông tin ảnh")
            info_window.geometry("500x600")
            info_window.resizable(False, False)

            frame = tk.Frame(info_window, padx=15, pady=15)
            frame.pack(fill=tk.BOTH, expand=True)

            info_text = f'''
Tên file:
{file_name}

Đường dẫn:
{self.gif_path}

Kích thước:
{width} x {height}

Dung lượng:
{file_size:.2f} KB

Bảng màu:
{color_mode}

Số frame:
{total_frames}

Thời lượng:
{total_duration_sec:.2f} giây
'''

            label = tk.Label(
                frame,
                text=info_text,
                justify="left",
                anchor="w",
                font=("Segoe UI", 10)
            )
            label.pack(fill=tk.X)

            def open_location():
                system = platform.system()

                if system == "Windows":
                    subprocess.run(f'explorer /select,"{self.gif_path}"')
                elif system == "Darwin":
                    subprocess.run(["open", "-R", self.gif_path])
                else:
                    subprocess.run(["xdg-open", folder_path])

            open_btn = tk.Button(
                frame,
                text="📂 Open in location",
                command=open_location
            )
            open_btn.pack(pady=15)

        except Exception as e:
            messagebox.showerror("Lỗi", str(e))

    def on_closing(self):
        """Xử lý khi tắt ứng dụng"""
        # Kiểm tra có thay đổi chưa lưu
        if self.gif_frames and self.history_index != self.saved_history_index:
            # Có thay đổi, hỏi lưu
            if not self.ask_save_changes():
                return  # Huỷ đóng
        
        # Cleanup
        self.is_playing = False
        if self.animation_id:
            self.root.after_cancel(self.animation_id)
        if self.zoom_pan_timer:
            self.root.after_cancel(self.zoom_pan_timer)
        self.stop_resize_thread = True
        self.root.quit()
    
    def ask_save_changes(self):
        """
        Hỏi lưu thay đổi.
        Trả về True nếu tiếp tục đóng app, False nếu hủy
        """
        dialog = tk.Toplevel(self.root)
        dialog.title("Unsaved Changes")
        dialog.geometry("450x150")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Result variable
        result = {'value': None}
        
        # Message
        msg_label = tk.Label(
            dialog,
            text="You haven't saved your changes.\nDo you want to save them?",
            font=("Arial", 11),
            justify="center"
        )
        msg_label.pack(pady=20)
        
        # Button frame
        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=10)
        
        def on_save():
            result['value'] = 'save'
            dialog.destroy()
        
        def on_save_as():
            result['value'] = 'save_as'
            dialog.destroy()
        
        def on_dont_save():
            result['value'] = 'dont_save'
            dialog.destroy()
        
        def on_cancel():
            result['value'] = 'cancel'
            dialog.destroy()
        
        # Buttons
        save_btn = tk.Button(btn_frame, text="Save", command=on_save, width=12)
        save_btn.grid(row=0, column=0, padx=5)
        
        save_as_btn = tk.Button(btn_frame, text="Save As", command=on_save_as, width=12)
        save_as_btn.grid(row=0, column=1, padx=5)
        
        dont_save_btn = tk.Button(btn_frame, text="Don't Save", command=on_dont_save, width=12)
        dont_save_btn.grid(row=0, column=2, padx=5)
        
        cancel_btn = tk.Button(btn_frame, text="Cancel", command=on_cancel, width=12)
        cancel_btn.grid(row=0, column=3, padx=5)
        
        # Wait for user response
        self.root.wait_window(dialog)
        
        # Handle result
        if result['value'] == 'save':
            self.save_file()
            return True
        elif result['value'] == 'save_as':
            self.save_file_as()
            return True
        elif result['value'] == 'dont_save':
            return True
        else:  # cancel
            return False
    
    def create_canvas(self):
        """Tạo canvas hiển thị GIF"""
        self.canvas = tk.Canvas(
            self.root, 
            bg="gray20", 
            cursor="hand2",
            highlightthickness=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Bind events
        self.canvas.bind("<MouseWheel>", self.on_scroll)
        self.canvas.bind("<Button-4>", self.on_scroll)  # Linux scroll up
        self.canvas.bind("<Button-5>", self.on_scroll)  # Linux scroll down
        self.canvas.bind("<Button-1>", self.on_mouse_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_release)
    
    def create_controls(self):
        """Tạo thanh control"""
        # Top control frame
        top_frame = tk.Frame(self.root)
        top_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Play/Pause button
        self.play_pause_btn = tk.Button(
            top_frame, 
            text="⏸ Pause", 
            command=self.toggle_play_pause,
            width=10
        )
        self.play_pause_btn.pack(side=tk.LEFT, padx=5)
        
        # Info label
        self.info_label = tk.Label(
            top_frame, 
            text="Chưa mở file GIF",
            fg="gray"
        )
        self.info_label.pack(side=tk.LEFT, padx=10)
        
        # Speed control
        speed_label = tk.Label(top_frame, text="Speed:")
        speed_label.pack(side=tk.LEFT, padx=5)
        
        self.speed_var = tk.DoubleVar(value=1.0)
        speed_scale = tk.Scale(
            top_frame,
            from_=0.25,
            to=2.0,
            resolution=0.25,
            orient=tk.HORIZONTAL,
            variable=self.speed_var,
            command=self.on_speed_change,
            length=150,
            bg="gray30",
            fg="white"
        )
        speed_scale.pack(side=tk.LEFT, padx=5)
        
        self.speed_label = tk.Label(top_frame, text="1.0x", width=4)
        self.speed_label.pack(side=tk.LEFT, padx=5)
        
        # Loop button
        self.loop_btn = tk.Button(
            top_frame,
            text="🔁 Loop",
            command=self.toggle_loop,
            width=8
        )
        self.loop_btn.pack(side=tk.LEFT, padx=5)
        
        # Bottom frame for scrubbar
        bottom_frame = tk.Frame(self.root)
        bottom_frame.pack(fill=tk.X, padx=5, pady=5)
        
        frame_info_label = tk.Label(bottom_frame, text="Frame:")
        frame_info_label.pack(side=tk.LEFT, padx=5)
        
        self.frame_scale = tk.Scale(
            bottom_frame,
            from_=0,
            to=1,
            orient=tk.HORIZONTAL,
            command=self.on_scrub_change,
            length=500,
            bg="gray30",
            fg="white"
        )
        self.frame_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        self.frame_label = tk.Label(bottom_frame, text="0/0", width=10)
        self.frame_label.pack(side=tk.LEFT, padx=5)
    
    def on_speed_change(self, value):
        """Xử lý thay đổi speed"""
        self.speed_level = float(value)
        self.speed_label.config(text=f"{self.speed_level:.2f}x")
    
    def toggle_loop(self):
        """Chuyển đổi loop mode"""
        self.is_looping = not self.is_looping
        if self.is_looping:
            self.loop_btn.config(text="🔁 Loop")
        else:
            self.loop_btn.config(text="⏹️ No Loop")
    
    def on_scrub_change(self, value):
        """Xử lý kéo thanh tua"""
        if not self.gif_frames:
            return
        
        frame_index = int(float(value))
        if frame_index != self.current_frame:
            self.current_frame = frame_index
            self.start_time = None  # Reset timing khi user kéo thanh tua
            self.update_frame()

    
    def open_file(self):
        """Mở file GIF"""
        file_path = filedialog.askopenfilename(
            filetypes=[("GIF files", "*.gif"), ("All files", "*.*")],
            initialdir=os.path.expanduser("~")
        )
        
        if file_path:
            try:
                self.gif_path = file_path
                self.load_gif()
                self.reset_view()
                self.update_frame()
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể mở file: {str(e)}")
    
    def save_file(self):
        """Lưu GIF hiện tại vào file đang mở"""
        if not self.gif_frames:
            messagebox.showwarning("Cảnh báo", "Không có GIF nào để lưu!")
            return

        if not self.gif_path:
            self.save_file_as()
            return

        try:
            self._save_gif_to_path(self.gif_path)
            # Cập nhật saved index
            self.saved_history_index = self.history_index
            messagebox.showinfo("Thành công", f"Đã lưu vào:\n{self.gif_path}")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể lưu file: {str(e)}")

    def save_file_as(self):
        """Lưu GIF với tên file mới"""
        if not self.gif_frames:
            messagebox.showwarning("Cảnh báo", "Không có GIF nào để lưu!")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".gif",
            filetypes=[("GIF files", "*.gif"), ("All files", "*.*")],
            initialdir=os.path.dirname(self.gif_path) if self.gif_path else os.path.expanduser("~"),
            initialfile=os.path.basename(self.gif_path) if self.gif_path else "output.gif"
        )

        if file_path:
            try:
                self._save_gif_to_path(file_path)
                self.gif_path = file_path
                # Cập nhật saved index
                self.saved_history_index = self.history_index
                messagebox.showinfo("Thành công", f"Đã lưu vào:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể lưu file: {str(e)}")

    def _save_gif_to_path(self, file_path):
        """Xuất danh sách frame hiện tại thành GIF"""
        if not self.gif_frames:
            raise ValueError("Không có frame để lưu")

        frames_to_save = self.source_frames if self.source_frames else self.gif_frames
        save_gif_frames(frames_to_save, self.frame_durations, file_path, loop=0)
    
    def load_gif(self):
        """Load tất cả frame của GIF"""
        self.gif_frames = []
        self.source_frames = []
        self.frame_durations = []
        # Reset history khi load file mới
        self.history_stack = []
        self.history_index = -1
        self.saved_history_index = -1
        try:
            gif = Image.open(self.gif_path)
            
            for frame_index in range(gif.n_frames):
                gif.seek(frame_index)
                duration = gif.info.get('duration', 100)
                self.frame_durations.append(float(duration))  # Lưu dạng float để chính xác

                source_frame = gif.convert('RGBA')
                self.source_frames.append(source_frame)
                
                # Xử lý transparency cho phần hiển thị
                alpha_min = source_frame.getchannel('A').getextrema()[0]
                if alpha_min < 255:
                    # Tạo background caro
                    background = self.create_checkerboard(source_frame.size)
                    background.paste(source_frame, (0, 0), source_frame)
                    frame = background.convert('RGB')
                else:
                    frame = source_frame.convert('RGB')
                
                self.gif_frames.append(frame)
            
            self.current_frame = 0
            self.start_time = None
            self.total_duration = 0.0
            
            # Update scrubbar
            self.frame_scale.config(to=len(self.gif_frames) - 1)
            self.frame_scale.set(0)
            
            filename = os.path.basename(self.gif_path)
            avg_duration = sum(self.frame_durations) / len(self.frame_durations)
            self.info_label.config(
                text=f"{filename} | Frames: {len(self.gif_frames)} | Duration: {avg_duration:.0f}ms"
            )
            self.update_frame_label()
            # Lưu trạng thái "raw" vào history
            self.save_state_to_history()
            # Đặt saved index = history index (lúc vừa load, chưa có thay đổi)
            self.saved_history_index = self.history_index
            self.start_resize_thread()
        except Exception as e:
            messagebox.showerror("Lỗi", f"Lỗi load GIF: {str(e)}")

    def create_checkerboard(self, size, square_size=10):
        """Tạo background caro cho transparency"""
        width, height = size
        board = Image.new('RGB', size, 'white')
        pixels = board.load()
        
        light_gray = (200, 200, 200)
        for y in range(height):
            for x in range(width):
                if ((x // square_size) + (y // square_size)) % 2 == 0:
                    pixels[x, y] = light_gray
        
        return board
    
    def update_frame_label(self):
        """Cập nhật label hiển thị frame hiện tại"""
        if self.gif_frames:
            self.frame_label.config(
                text=f"{self.current_frame + 1}/{len(self.gif_frames)}"
            )

    
    def update_frame(self):
        """Cập nhật frame hiển thị với time-based tracking"""
        if not self.gif_frames or self.is_updating_frame:
            return
        
        # Clear debounce timer
        if self.zoom_pan_timer:
            self.root.after_cancel(self.zoom_pan_timer)
            self.zoom_pan_timer = None
        
        self.is_updating_frame = True
        try:
            # Nếu vừa bắt đầu play, ghi nhận start time
            if self.is_playing and self.start_time is None:
                self.start_time = time.time()
                self.total_duration = 0.0
            
            # Tính frame nào cần hiển thị dựa trên elapsed time
            if self.is_playing:
                elapsed_ms = (time.time() - self.start_time) * 1000 * self.speed_level
                
                # Tìm frame tương ứng với elapsed time
                current_duration = 0.0
                for i, frame_duration in enumerate(self.frame_durations):
                    if current_duration + frame_duration > elapsed_ms:
                        self.current_frame = i
                        break
                    current_duration += frame_duration
                else:
                    # Loop lại hoặc dừng nếu không loop
                    if self.is_looping:
                        self.current_frame = 0
                        self.start_time = time.time()
                    else:
                        # Dừng ở frame cuối cùng
                        self.current_frame = len(self.gif_frames) - 1
                        self.is_playing = False
                        self.play_pause_btn.config(text="▶ Play")
            
            # Lấy frame hiện tại
            frame = self.gif_frames[self.current_frame]
            
            # Áp dụng zoom
            new_width = int(frame.width * self.zoom_level)
            new_height = int(frame.height * self.zoom_level)
            
            # Cache key cho resized frame
            cache_key = (self.current_frame, new_width, new_height)
            
            # Kiểm tra cache
            if cache_key in self.resized_frame_cache:
                frame_resized = self.resized_frame_cache[cache_key]
            else:
                # Queue task để resize trên background thread
                try:
                    self.render_queue.put_nowait((self.current_frame, frame, new_width, new_height))
                except queue.Full:
                    pass
                
                # NEVER block main thread - use previous frame if available
                # Thay vì resize on main thread, skip frame hoặc use fallback
                fallback_key = None
                for cached_key in sorted(self.resized_frame_cache.keys(), 
                                        key=lambda k: abs(k[1]-new_width) + abs(k[2]-new_height)):
                    if cached_key[0] == self.current_frame:
                        fallback_key = cached_key
                        break
                
                if fallback_key:
                    frame_resized = self.resized_frame_cache[fallback_key]
                else:
                    # Use fastest resampling to minimize delay
                    resample = Image.Resampling.NEAREST if self.zoom_level <= 1.5 else Image.Resampling.NEAREST
                    frame_resized = frame.resize((new_width, new_height), resample)
            
            # Convert to PhotoImage
            self.display_image = ImageTk.PhotoImage(frame_resized)
            
            # Xóa image cũ
            self.canvas.delete("image")
            
            # Hiển thị image mới
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            
            if canvas_width <= 1:
                canvas_width = 800
            if canvas_height <= 1:
                canvas_height = 600
            
            # Vị trí center + pan offset
            x = canvas_width // 2 + self.pan_x
            y = canvas_height // 2 + self.pan_y
            
            self.canvas.create_image(
                x, y,
                image=self.display_image,
                tag="image"
            )
            
            # Update frame label
            self.update_frame_label()
            self.frame_scale.set(self.current_frame)
            
            # Schedule next update với fixed interval (16ms = 60fps max)
            # Cancel any pending animation callbacks first
            if self.animation_id:
                self.root.after_cancel(self.animation_id)
                self.animation_id = None
            
            if self.is_playing and self.gif_frames:
                self.animation_id = self.root.after(16, self.update_frame)
        finally:
            self.is_updating_frame = False
    
    def on_scroll(self, event):
        """Xử lý scroll để zoom"""
        if not self.gif_frames:
            return
        
        # Kiểm hướng scroll
        if event.num == 5 or event.delta < 0:  # Scroll down
            self.zoom_level *= 0.9
        else:  # Scroll up
            self.zoom_level *= 1.1
        
        # Giới hạn zoom
        self.zoom_level = max(0.1, min(5.0, self.zoom_level))
        
        # Debounce: cancel previous timer and schedule new update
        if self.zoom_pan_timer:
            self.root.after_cancel(self.zoom_pan_timer)
        self.zoom_pan_timer = self.root.after(50, self.update_frame)
    
    def on_mouse_press(self, event):
        """Bắt đầu drag"""
        self.is_dragging = True
        self.last_mouse_x = event.x
        self.last_mouse_y = event.y
    
    def on_mouse_drag(self, event):
        """Drag để di chuyển"""
        if self.is_dragging and self.gif_frames:
            delta_x = event.x - self.last_mouse_x
            delta_y = event.y - self.last_mouse_y
            
            self.pan_x += delta_x
            self.pan_y += delta_y
            
            self.last_mouse_x = event.x
            self.last_mouse_y = event.y
            
            # Debounce: cancel previous timer and schedule new update
            if self.zoom_pan_timer:
                self.root.after_cancel(self.zoom_pan_timer)
            self.zoom_pan_timer = self.root.after(30, self.update_frame)
    
    def on_mouse_release(self, event):
        """Kết thúc drag"""
        self.is_dragging = False
    
    def zoom_in(self):
        """Phóng to"""
        if self.gif_frames:
            self.zoom_level *= 1.2
            self.zoom_level = min(5.0, self.zoom_level)
            # Don't clear entire cache, let background thread handle it
            self.update_frame()
    
    def zoom_out(self):
        """Thu nhỏ"""
        if self.gif_frames:
            self.zoom_level *= 0.8
            self.zoom_level = max(0.1, self.zoom_level)
            # Don't clear entire cache, let background thread handle it
            self.update_frame()
    
    def fit_to_window(self):
        """Fit GIF vào cửa sổ"""
        if not self.gif_frames:
            return
        
        frame = self.gif_frames[0]
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        if canvas_width <= 1:
            canvas_width = 800
        if canvas_height <= 1:
            canvas_height = 600
        
        zoom_x = canvas_width / frame.width
        zoom_y = canvas_height / frame.height
        
        self.zoom_level = min(zoom_x, zoom_y) * 0.9
        self.pan_x = 0
        self.pan_y = 0
        self.update_frame()
    
    def reset_view(self):
        """Reset zoom và pan"""
        self.zoom_level = 1.0
        self.pan_x = 0
        self.pan_y = 0
        if self.gif_frames:
            self.update_frame()
    
    def toggle_play_pause(self):
        """Chuyển đổi play/pause"""
        self.is_playing = not self.is_playing
        
        if self.is_playing:
            self.play_pause_btn.config(text="⏸ Pause")
            # Reset time khi play lại
            self.start_time = None
            if self.animation_id is None:
                self.update_frame()
        else:
            self.play_pause_btn.config(text="▶ Play")
            # Reset time khi pause
            self.start_time = None
            if self.animation_id:
                self.root.after_cancel(self.animation_id)
                self.animation_id = None
    
    def save_state_to_history(self):
        """Lưu trạng thái GIF hiện tại vào history"""
        if not self.gif_frames:
            return
        
        # Nếu đang ở giữa history (đã undo), xóa các trạng thái redo
        if self.history_index < len(self.history_stack) - 1:
            self.history_stack = self.history_stack[:self.history_index + 1]
        
        # Lưu trạng thái hiện tại (deep copy)
        state = {
            'gif_frames': [frame.copy() for frame in self.gif_frames],
            'source_frames': [frame.copy() for frame in self.source_frames] if self.source_frames else [],
            'frame_durations': self.frame_durations.copy(),
            'current_frame': self.current_frame
        }
        
        self.history_stack.append(state)
        self.history_index = len(self.history_stack) - 1
    
    def undo(self):
        """Hoàn tác thao tác cuối cùng"""
        if not self.gif_frames or self.history_index <= 0:
            messagebox.showinfo("Undo", "Không có thao tác nào để hoàn tác!")
            return
        
        self.history_index -= 1
        self.restore_state_from_history()
    
    def redo(self):
        """Làm lại thao tác đã hoàn tác"""
        if not self.gif_frames or self.history_index >= len(self.history_stack) - 1:
            messagebox.showinfo("Redo", "Không có thao tác nào để làm lại!")
            return
        
        self.history_index += 1
        self.restore_state_from_history()
    
    def restore_state_from_history(self):
        """Khôi phục trạng thái từ history"""
        if 0 <= self.history_index < len(self.history_stack):
            state = self.history_stack[self.history_index]
            
            # Khôi phục các frame
            self.gif_frames = [frame.copy() for frame in state['gif_frames']]
            self.source_frames = [frame.copy() for frame in state['source_frames']] if state['source_frames'] else []
            self.frame_durations = state['frame_durations'].copy()
            self.current_frame = state['current_frame']
            
            # Reset cache và cập nhật UI
            self.resized_frame_cache.clear()
            self.frame_scale.config(to=len(self.gif_frames) - 1)
            self.start_time = None
            self.update_frame()
    
    def open_crop_dialog(self):
        """Mở dialog crop GIF"""
        if not self.gif_frames:
            messagebox.showwarning("Cảnh báo", "Vui lòng mở file GIF trước!")
            return
        
        CropDialog(self.root, self.gif_frames, self.apply_crop)
    
    def apply_crop(self, crop_box):
        """Áp dụng crop vào GIF"""
        try:
            
            left, top, right, bottom = crop_box

            if right <= left or bottom <= top:
                messagebox.showerror("Lỗi", "Crop box không hợp lệ")
                return

            cropped_frames = []
            cropped_source_frames = []
            cropped_durations = []

            source_frames = self.source_frames if self.source_frames else self.gif_frames
            for frame, source_frame, duration in zip(self.gif_frames, source_frames, self.frame_durations):
                cropped_frame = frame.crop((left, top, right, bottom))
                cropped_source = source_frame.crop((left, top, right, bottom))
                cropped_frames.append(cropped_frame)
                cropped_source_frames.append(cropped_source)
                cropped_durations.append(duration)

            self.gif_frames = cropped_frames
            self.source_frames = cropped_source_frames
            self.frame_durations = cropped_durations
            self.current_frame = 0
            self.start_time = None
            self.resized_frame_cache.clear()

            self.frame_scale.config(to=len(self.gif_frames) - 1)
            self.frame_scale.set(0)

            messagebox.showinfo("Thành công", "Crop thành công!")
            self.update_frame()
            self.save_state_to_history()
        except Exception as e:
            messagebox.showerror("Lỗi", f"Lỗi crop GIF: {str(e)}")

    def open_trim_dialog(self):
        """Mở dialog trim GIF"""
        if not self.gif_frames:
            messagebox.showwarning("Cảnh báo", "Vui lòng mở file GIF trước!")
            return
        
        TrimDialog(self.root, len(self.gif_frames), self.apply_trim)
    
    def apply_trim(self, start_frame, end_frame):
        """Áp dụng trim vào GIF"""
        try:
            
            if start_frame < 0 or end_frame > len(self.gif_frames) or start_frame >= end_frame:
                messagebox.showerror("Lỗi", "Frame range không hợp lệ")
                return
            
            # Trim frame
            self.gif_frames = self.gif_frames[start_frame:end_frame]
            self.source_frames = self.source_frames[start_frame:end_frame] if self.source_frames else []
            self.frame_durations = self.frame_durations[start_frame:end_frame]
            self.current_frame = 0
            self.start_time = None
            self.resized_frame_cache.clear()
            
            self.frame_scale.config(to=len(self.gif_frames) - 1)
            self.frame_scale.set(0)
            
            messagebox.showinfo("Thành công", f"Trim thành công! Giữ lại {len(self.gif_frames)} frame")
            self.update_frame()
            self.save_state_to_history()
        except Exception as e:
            messagebox.showerror("Lỗi", f"Lỗi trim GIF: {str(e)}")
    
    def open_resize_dialog(self):
        """Mở dialog resize GIF"""
        if not self.gif_frames:
            messagebox.showwarning("Cảnh báo", "Vui lòng mở file GIF trước!")
            return

        first_frame = self.gif_frames[0]

        ResizeDialog(
            self.root,
            first_frame.width,
            first_frame.height,
            self.apply_resize
        )
    def apply_resize(self, new_width, new_height):
        """Resize toàn bộ GIF"""

        try:
            
            if new_width <= 0 or new_height <= 0:
                messagebox.showerror("Lỗi", "Kích thước không hợp lệ")
                return

            resized_frames = []
            resized_source_frames = []

            source_frames = self.source_frames if self.source_frames else self.gif_frames

            for frame, source_frame in zip(self.gif_frames, source_frames):

                resized_frame = frame.resize(
                    (new_width, new_height),
                    Image.Resampling.LANCZOS
                )

                resized_source = source_frame.resize(
                (new_width, new_height),
                Image.Resampling.LANCZOS
                )

                resized_frames.append(resized_frame)
                resized_source_frames.append(resized_source)

            self.gif_frames = resized_frames
            self.source_frames = resized_source_frames

            self.current_frame = 0
            self.start_time = None
            self.resized_frame_cache.clear()

            messagebox.showinfo(
                "Thành công",
                f"Đã resize GIF thành {new_width}x{new_height}"
            )

            self.update_frame()
            self.save_state_to_history()

        except Exception as e:
            messagebox.showerror("Lỗi", f"Lỗi resize GIF: {str(e)}")
    def show_help(self):
        """Hiển thị hướng dẫn sử dụng"""

        help_text = """
ANIMATED - HƯỚNG DẪN

━━━━━━━━━━━━━━━━━━
📂 MỞ GIF
━━━━━━━━━━━━━━━━━━

• File → Mở file GIF
• Hoặc kéo & thả file trực tiếp vào cửa sổ

━━━━━━━━━━━━━━━━━━
🎞 PLAYBACK
━━━━━━━━━━━━━━━━━━

• Space:
  Play / Pause GIF

• ← / →:
  Chuyển frame thủ công khi đang pause

• Thanh scrubbar:
  Kéo để tua đến frame bất kỳ

• Speed slider:
  Điều chỉnh tốc độ từ 0.25x → 2.0x

━━━━━━━━━━━━━━━━━━
🔍 VIEW CONTROLS
━━━━━━━━━━━━━━━━━━

• Scroll chuột:
  Zoom in / Zoom out

• Click + Drag:
  Di chuyển ảnh

• View → Fit to window:
  Fit GIF vào cửa sổ

• View → Reset:
  Reset zoom & vị trí

━━━━━━━━━━━━━━━━━━
✂ EDITING
━━━━━━━━━━━━━━━━━━
• Edit → Undo
  Hoàn tác thay đổ

• Edit → Redo
  Làm lại thay đổi

• Edit → Crop
  Crop GIF bằng preview box trực quan

• Edit → Trim
  Cắt frame theo khoảng mong muốn

• Edit → Resize
  Thay đổi kích thước ảnh

━━━━━━━━━━━━━━━━━━
🧩 TRANSPARENCY
━━━━━━━━━━━━━━━━━━

• GIF transparent sẽ hiển thị nền caro
• Khi lưu, transparency được giữ nguyên

━━━━━━━━━━━━━━━━━━
ℹ IMAGE INFO
━━━━━━━━━━━━━━━━━━

File → Thông tin ảnh

Hiển thị:
• đường dẫn file
• kích thước ảnh
• dung lượng KB
• color mode (RGBA/P)
• số frame
• thời lượng GIF

━━━━━━━━━━━━━━━━━━
⌨ SHORTCUTS
━━━━━━━━━━━━━━━━━━

Ctrl+O       → Mở file
Space        → Play/Pause
Mouse Wheel  → Zoom
Left Arrow   → Previous frame
Right Arrow  → Next frame
Ctrl+S       → Lưu
Ctrl+Shift+S → Lưu thành
Ctrl+Z       → Undo
Ctrl+Y       → Redo

━━━━━━━━━━━━━━━━━━
🐍 TECH
━━━━━━━━━━━━━━━━━━

Python + Tkinter + Pillow
with suspicious amounts of GIF energy
"""

        help_window = tk.Toplevel(self.root)
        help_window.title("Hướng dẫn")
        help_window.geometry("720x650")
        help_window.configure(bg="#2b2b2b")

        text_widget = tk.Text(
            help_window,
            wrap="word",
            bg="#2b2b2b",
            fg="#dddddd",
            font=("Consolas", 10),
            relief="flat",
            padx=15,
            pady=15
        )

        text_widget.insert("1.0", help_text)
        text_widget.config(state="disabled")
        text_widget.pack(fill=tk.BOTH, expand=True)
    
    def show_about(self):
        """Hiển thị thông tin chương trình"""
    
        about_window = tk.Toplevel(self.root)
        about_window.title("About GIF Viewer")
        about_window.geometry("420x320")
        about_window.resizable(False, False)
        about_window.configure(bg="#2b2b2b")

        # Title
        title_label = tk.Label(
            about_window,
            text="Animated",
            font=("Segoe UI", 20, "bold"),
            fg="white",
            bg="#2b2b2b"
        )
        title_label.pack(pady=(20, 5))

        version_label = tk.Label(
            about_window,
            text="Version 1.0.0",
            font=("Segoe UI", 10),
            fg="#aaaaaa",
            bg="#2b2b2b"
        )
        version_label.pack()

        desc = """
A classic GIF viewer built with Python + Tkinter.

Features:
• Smooth playback
• Zoom & pan
• Frame scrubbing
• Crop & trim
• Transparent GIF support
• Drag & drop
• Adjustable playback speed

Made with questionable sleep schedules ☕
"""

        desc_label = tk.Label(
            about_window,
            text=desc,
            justify="left",
            font=("Consolas", 10),
            fg="#dddddd",
            bg="#2b2b2b"
        )
        desc_label.pack(padx=20, pady=20, anchor="w")

        close_btn = tk.Button(
            about_window,
            text="Close",
            command=about_window.destroy,
            width=10
        )
        close_btn.pack(pady=10)


class CropDialog:
    """Dialog để crop GIF"""
    def __init__(self, parent, gif_frames, callback):
        self.gif_frames = gif_frames
        self.callback = callback

        first_frame = gif_frames[0]
        self.frame_width = first_frame.width
        self.frame_height = first_frame.height

        max_canvas_width = 800
        max_canvas_height = 500
        aspect_ratio = self.frame_width / self.frame_height

        if aspect_ratio > max_canvas_width / max_canvas_height:
            self.canvas_width = max_canvas_width
            self.canvas_height = int(max_canvas_width / aspect_ratio)
        else:
            self.canvas_height = max_canvas_height
            self.canvas_width = int(max_canvas_height * aspect_ratio)

        self.scale_x = self.canvas_width / self.frame_width
        self.scale_y = self.canvas_height / self.frame_height

        # Crop box in original coordinates: left, top, right, bottom
        self.crop_left = 0
        self.crop_top = 0
        self.crop_right = self.frame_width
        self.crop_bottom = self.frame_height

        self.handle_size = 8
        self.is_dragging_handle = None
        self.asymmetric_resize = False
        self.min_size = 20

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Crop GIF")
        self.dialog.geometry(f"{self.canvas_width + 100}x{self.canvas_height + 250}")
        self.dialog.resizable(False, False)

        control_frame = tk.Frame(self.dialog)
        control_frame.pack(pady=5, padx=10, fill=tk.X)

        self.preview_canvas = tk.Canvas(
            self.dialog,
            bg="gray30",
            width=self.canvas_width,
            height=self.canvas_height,
            cursor="crosshair"
        )
        self.preview_canvas.pack(pady=10, padx=10)

        self.preview_canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.preview_canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.preview_canvas.bind("<Motion>", self.on_canvas_move)

        self.display_image = self.prepare_frame_image(first_frame)
        self.canvas_image_id = self.preview_canvas.create_image(
            0, 0, anchor="nw", image=self.display_image, tag="frame_image"
        )

        self.draw_crop_box()

        input_frame = tk.Frame(self.dialog)
        input_frame.pack(pady=10, padx=10, fill=tk.X)

        tk.Label(input_frame, text="Left:").grid(row=0, column=0, sticky="w", padx=5)
        self.left_var = tk.StringVar(value=str(self.crop_left))
        left_entry = tk.Entry(input_frame, textvariable=self.left_var, width=10)
        left_entry.grid(row=0, column=1, padx=5)
        left_entry.bind("<KeyRelease>", lambda e: self.on_input_change())

        tk.Label(input_frame, text="Top:").grid(row=0, column=2, sticky="w", padx=5)
        self.top_var = tk.StringVar(value=str(self.crop_top))
        top_entry = tk.Entry(input_frame, textvariable=self.top_var, width=10)
        top_entry.grid(row=0, column=3, padx=5)
        top_entry.bind("<KeyRelease>", lambda e: self.on_input_change())

        tk.Label(input_frame, text="Right:").grid(row=1, column=0, sticky="w", padx=5)
        self.right_var = tk.StringVar(value=str(self.crop_right))
        right_entry = tk.Entry(input_frame, textvariable=self.right_var, width=10)
        right_entry.grid(row=1, column=1, padx=5)
        right_entry.bind("<KeyRelease>", lambda e: self.on_input_change())

        tk.Label(input_frame, text="Bottom:").grid(row=1, column=2, sticky="w", padx=5)
        self.bottom_var = tk.StringVar(value=str(self.crop_bottom))
        bottom_entry = tk.Entry(input_frame, textvariable=self.bottom_var, width=10)
        bottom_entry.grid(row=1, column=3, padx=5)
        bottom_entry.bind("<KeyRelease>", lambda e: self.on_input_change())

        button_frame = tk.Frame(self.dialog)
        button_frame.pack(pady=10, fill=tk.X, padx=10)

        tk.Button(button_frame, text="Crop", command=self.apply_crop).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def prepare_frame_image(self, frame):
        """Chuẩn bị frame để hiển thị"""
        resized = frame.resize(
            (self.canvas_width, self.canvas_height),
            Image.Resampling.LANCZOS
        )
        return ImageTk.PhotoImage(resized)

    def _sync_inputs(self):
        self.left_var.set(str(int(self.crop_left)))
        self.top_var.set(str(int(self.crop_top)))
        self.right_var.set(str(int(self.crop_right)))
        self.bottom_var.set(str(int(self.crop_bottom)))

    def _clamp_box(self, active_handle=None):
        """Clamp crop box to frame boundaries and keep minimum size."""
        left = int(self.crop_left)
        top = int(self.crop_top)
        right = int(self.crop_right)
        bottom = int(self.crop_bottom)

        if right < left:
            left, right = right, left
        if bottom < top:
            top, bottom = bottom, top

        if right - left < self.min_size:
            if active_handle in {"left", "tl", "bl"}:
                left = right - self.min_size
            else:
                right = left + self.min_size

        if bottom - top < self.min_size:
            if active_handle in {"top", "tl", "tr"}:
                top = bottom - self.min_size
            else:
                bottom = top + self.min_size

        if left < 0:
            shift = -left
            left += shift
            right += shift
        if top < 0:
            shift = -top
            top += shift
            bottom += shift
        if right > self.frame_width:
            shift = right - self.frame_width
            right -= shift
            left -= shift
        if bottom > self.frame_height:
            shift = bottom - self.frame_height
            bottom -= shift
            top -= shift

        left = max(0, left)
        top = max(0, top)
        right = min(self.frame_width, right)
        bottom = min(self.frame_height, bottom)

        if right - left < self.min_size:
            if left + self.min_size <= self.frame_width:
                right = left + self.min_size
            else:
                left = self.frame_width - self.min_size
                right = self.frame_width

        if bottom - top < self.min_size:
            if top + self.min_size <= self.frame_height:
                bottom = top + self.min_size
            else:
                top = self.frame_height - self.min_size
                bottom = self.frame_height

        self.crop_left = int(left)
        self.crop_top = int(top)
        self.crop_right = int(right)
        self.crop_bottom = int(bottom)

    def draw_crop_box(self):
        """Vẽ crop box và overlay tối"""
        self.preview_canvas.delete("overlay", "crop_box", "handles")

        x1_canvas = self.crop_left * self.scale_x
        y1_canvas = self.crop_top * self.scale_y
        x2_canvas = self.crop_right * self.scale_x
        y2_canvas = self.crop_bottom * self.scale_y

        if y1_canvas > 0:
            self.preview_canvas.create_rectangle(
                0, 0, self.canvas_width, y1_canvas,
                fill="black", stipple="gray50", tag="overlay"
            )

        if y2_canvas < self.canvas_height:
            self.preview_canvas.create_rectangle(
                0, y2_canvas, self.canvas_width, self.canvas_height,
                fill="black", stipple="gray50", tag="overlay"
            )

        if x1_canvas > 0:
            self.preview_canvas.create_rectangle(
                0, y1_canvas, x1_canvas, y2_canvas,
                fill="black", stipple="gray50", tag="overlay"
            )

        if x2_canvas < self.canvas_width:
            self.preview_canvas.create_rectangle(
                x2_canvas, y1_canvas, self.canvas_width, y2_canvas,
                fill="black", stipple="gray50", tag="overlay"
            )

        self.preview_canvas.create_rectangle(
            x1_canvas, y1_canvas, x2_canvas, y2_canvas,
            outline="yellow", width=2, tag="crop_box"
        )

        handle_radius = self.handle_size
        corners = [
            (x1_canvas, y1_canvas, "tl"),
            (x2_canvas, y1_canvas, "tr"),
            (x1_canvas, y2_canvas, "bl"),
            (x2_canvas, y2_canvas, "br")
        ]

        for x, y, _corner in corners:
            self.preview_canvas.create_oval(
                x - handle_radius, y - handle_radius,
                x + handle_radius, y + handle_radius,
                fill="yellow", tag="handles"
            )

        edges = [
            ((x1_canvas + x2_canvas) / 2, y1_canvas, "top"),
            ((x1_canvas + x2_canvas) / 2, y2_canvas, "bottom"),
            (x1_canvas, (y1_canvas + y2_canvas) / 2, "left"),
            (x2_canvas, (y1_canvas + y2_canvas) / 2, "right")
        ]

        for x, y, _edge in edges:
            self.preview_canvas.create_rectangle(
                x - handle_radius, y - handle_radius,
                x + handle_radius, y + handle_radius,
                fill="cyan", tag="handles"
            )

        self.crop_canvas_coords = (x1_canvas, y1_canvas, x2_canvas, y2_canvas)

    def get_handle_at(self, canvas_x, canvas_y):
        """Kiểm tra handle nào được click"""
        if not hasattr(self, 'crop_canvas_coords'):
            return None

        x1, y1, x2, y2 = self.crop_canvas_coords
        threshold = self.handle_size + 5

        if abs(canvas_x - x1) < threshold and abs(canvas_y - y1) < threshold:
            return "tl"
        if abs(canvas_x - x2) < threshold and abs(canvas_y - y1) < threshold:
            return "tr"
        if abs(canvas_x - x1) < threshold and abs(canvas_y - y2) < threshold:
            return "bl"
        if abs(canvas_x - x2) < threshold and abs(canvas_y - y2) < threshold:
            return "br"

        if abs(canvas_y - y1) < threshold and x1 < canvas_x < x2:
            return "top"
        if abs(canvas_y - y2) < threshold and x1 < canvas_x < x2:
            return "bottom"
        if abs(canvas_x - x1) < threshold and y1 < canvas_y < y2:
            return "left"
        if abs(canvas_x - x2) < threshold and y1 < canvas_y < y2:
            return "right"

        if x1 < canvas_x < x2 and y1 < canvas_y < y2:
            return "move"

        return None

    def on_canvas_move(self, event):
        """Cập nhật cursor khi move"""
        handle = self.get_handle_at(event.x, event.y)
        cursors = {
            "tl": "top_left_corner",
            "tr": "top_right_corner",
            "bl": "bottom_left_corner",
            "br": "bottom_right_corner",
            "top": "top_side",
            "bottom": "bottom_side",
            "left": "left_side",
            "right": "right_side",
            "move": "hand2"
        }
        self.preview_canvas.config(cursor=cursors.get(handle, "crosshair"))

    def on_canvas_drag(self, event):
        """Xử lý drag handle"""

        if not hasattr(self, 'crop_canvas_coords'):
            return

        if not hasattr(self, 'last_canvas_x'):
            self.last_canvas_x = event.x
            self.last_canvas_y = event.y
            self.is_dragging_handle = self.get_handle_at(event.x, event.y)
            return

        handle = self.is_dragging_handle

        if handle is None:
            return

        dx = int((event.x - self.last_canvas_x) / self.scale_x)
        dy = int((event.y - self.last_canvas_y) / self.scale_y)

        if handle == "left":
            self.crop_left += dx

        elif handle == "right":
            self.crop_right += dx

        elif handle == "top":
            self.crop_top += dy

        elif handle == "bottom":
            self.crop_bottom += dy

        elif handle == "tl":
            self.crop_left += dx
            self.crop_top += dy

        elif handle == "tr":
            self.crop_right += dx
            self.crop_top += dy

        elif handle == "bl":
            self.crop_left += dx
            self.crop_bottom += dy

        elif handle == "br":
            self.crop_right += dx
            self.crop_bottom += dy

        elif handle == "move":
            self.crop_left += dx
            self.crop_right += dx
            self.crop_top += dy
            self.crop_bottom += dy

        self._clamp_box(active_handle=handle)
        self._sync_inputs()

        self.last_canvas_x = event.x
        self.last_canvas_y = event.y

        self.draw_crop_box()

    def on_canvas_release(self, event):
        """Kết thúc drag"""
        self.is_dragging_handle = None
        if hasattr(self, 'last_canvas_x'):
            del self.last_canvas_x
            del self.last_canvas_y

    def on_input_change(self):
        """Cập nhật crop box khi input thay đổi"""
        try:
            self.crop_left = int(self.left_var.get())
            self.crop_top = int(self.top_var.get())
            self.crop_right = int(self.right_var.get())
            self.crop_bottom = int(self.bottom_var.get())

            self._clamp_box()
            self._sync_inputs()
            self.draw_crop_box()
        except ValueError:
            pass

    def apply_crop(self):
        """Áp dụng crop"""
        try:
            self._clamp_box()
            self.callback((
                self.crop_left,
                self.crop_top,
                self.crop_right,
                self.crop_bottom
            ))
            self.dialog.destroy()
        except Exception as e:
            messagebox.showerror("Lỗi", f"Lỗi: {str(e)}")

class ResizeDialog:
    """Dialog resize GIF"""

    def __init__(self, parent, current_width, current_height, callback):

        self.callback = callback
        self.aspect_ratio = current_width / current_height

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Resize GIF")
        self.dialog.geometry("300x180")
        self.dialog.resizable(False, False)

        frame = tk.Frame(self.dialog, padx=10, pady=10)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text="Width:").grid(row=0, column=0, sticky="w", pady=5)

        self.width_var = tk.StringVar(value=str(current_width))

        width_entry = tk.Entry(frame, textvariable=self.width_var)
        width_entry.grid(row=0, column=1, pady=5)

        tk.Label(frame, text="Height:").grid(row=1, column=0, sticky="w", pady=5)

        self.height_var = tk.StringVar(value=str(current_height))

        height_entry = tk.Entry(frame, textvariable=self.height_var)
        height_entry.grid(row=1, column=1, pady=5)

        self.keep_ratio_var = tk.BooleanVar(value=True)

        tk.Checkbutton(
            frame,
            text="Keep aspect ratio",
            variable=self.keep_ratio_var
        ).grid(row=2, columnspan=2, sticky="w", pady=10)

        self.width_var.trace_add("write", self.on_width_change)
        self.height_var.trace_add("write", self.on_height_change)

        button_frame = tk.Frame(frame)
        button_frame.grid(row=3, columnspan=2, pady=10)

        tk.Button(
            button_frame,
            text="Resize",
            command=self.apply_resize
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            button_frame,
            text="Cancel",
            command=self.dialog.destroy
        ).pack(side=tk.LEFT, padx=5)

        self.updating = False

    def on_width_change(self, *args):

        if self.updating or not self.keep_ratio_var.get():
            return

        try:
            self.updating = True

            width = int(self.width_var.get())
            height = int(width / self.aspect_ratio)

            self.height_var.set(str(height))

        except:
            pass
        finally:
            self.updating = False

    def on_height_change(self, *args):

        if self.updating or not self.keep_ratio_var.get():
            return

        try:
            self.updating = True

            height = int(self.height_var.get())
            width = int(height * self.aspect_ratio)

            self.width_var.set(str(width))

        except:
            pass
        finally:
            self.updating = False

    def apply_resize(self):

        try:
            width = int(self.width_var.get())
            height = int(self.height_var.get())

            self.callback(width, height)
            self.dialog.destroy()

        except ValueError:
            messagebox.showerror("Lỗi", "Vui lòng nhập số hợp lệ")

class TrimDialog:
    """Dialog để trim GIF"""
    def __init__(self, parent, total_frames, callback):
        self.total_frames = total_frames
        self.callback = callback
        
        # Dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Trim GIF")
        self.dialog.geometry("400x400")
        self.dialog.resizable(False, False)
        
        # Info
        info_label = tk.Label(self.dialog, text=f"Tổng frame: {total_frames}")
        info_label.pack(pady=10)
        
        # Input frame
        input_frame = tk.Frame(self.dialog)
        input_frame.pack(pady=10, padx=10, fill=tk.X)
        
        # Start frame
        tk.Label(input_frame, text="Frame bắt đầu (0):").pack(anchor="w", padx=5)
        self.start_var = tk.StringVar(value="0")
        tk.Entry(input_frame, textvariable=self.start_var, width=20).pack(anchor="w", padx=5, pady=5)
        
        # End frame
        tk.Label(input_frame, text=f"Frame kết thúc ({total_frames}):").pack(anchor="w", padx=5)
        self.end_var = tk.StringVar(value=str(total_frames))
        tk.Entry(input_frame, textvariable=self.end_var, width=20).pack(anchor="w", padx=5, pady=5)
        
        # Info text
        info_text = tk.Label(
            self.dialog, 
            text="Giữ lại frame từ start đến end (end không bao gồm)",
            fg="gray",
            font=("Arial", 9)
        )
        info_text.pack(pady=5)
        
        # Button frame
        button_frame = tk.Frame(self.dialog)
        button_frame.pack(pady=10, fill=tk.X, padx=10)
        
        tk.Button(button_frame, text="Trim", command=self.apply_trim).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def apply_trim(self):
        """Áp dụng trim"""
        try:
            start = int(self.start_var.get())
            end = int(self.end_var.get())
            
            if start < 0 or end > self.total_frames or start >= end:
                messagebox.showerror("Lỗi", "Frame range không hợp lệ")
                return
            
            self.callback(start, end)
            self.dialog.destroy()
        except ValueError:
            messagebox.showerror("Lỗi", "Vui lòng nhập số hợp lệ")


def main():
    root = TkinterDnD.Tk()
    app = GIFViewer(root)
    root.mainloop()


if __name__ == "__main__":
    main()
