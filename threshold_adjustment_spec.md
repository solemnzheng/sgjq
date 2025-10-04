# 阈值调节功能详细实现规范

## 功能概述
在应用程序顶部添加阈值调节区域，包含匹配阈值和NMS阈值的调节功能，以及清空信息按钮。该功能允许用户动态调整图像识别的敏感度。

## 界面布局规范

### 1. 框架设置
- 框架类型：ttk.Frame
- 高度：40像素
- 布局参数：
  - pack(fill="x", padx=10, pady=5)
  - pack_propagate(False)  # 禁用大小传播

### 2. 匹配阈值调节组件
#### 2.1 标签和输入框
- 标签文本："匹配阈值:"
- 输入框：
  - 类型：ttk.Entry
  - 宽度：5字符
  - 状态：readonly（只读）
  - 默认值："0.8"
  - 变量绑定：tk.StringVar(value="0.8")

#### 2.2 调节按钮
- 按钮类型：ttk.Button
- 宽度：2字符
- 文本：
  - 增加按钮："▲"
  - 减少按钮："▼"
- 功能：
  - 增加按钮：将匹配阈值增加0.1（上限0.9）
  - 减少按钮：将匹配阈值减少0.1（下限0.5）
- 布局：
  - 按钮框架内垂直排列
  - pady=0, padx=0, ipady=2

### 3. NMS阈值调节组件
#### 3.1 标签和输入框
- 标签文本："NMS阈值:"
- 输入框：
  - 类型：ttk.Entry
  - 宽度：5字符
  - 状态：readonly（只读）
  - 默认值："0.3"
  - 变量绑定：tk.StringVar(value="0.3")

#### 3.2 调节按钮
- 按钮类型：ttk.Button
- 宽度：2字符
- 文本：
  - 增加按钮："▲"
  - 减少按钮："▼"
- 功能：
  - 增加按钮：将NMS阈值增加0.1（上限0.9）
  - 减少按钮：将NMS阈值减少0.1（下限0.1）
- 布局：
  - 按钮框架内垂直排列
  - pady=0, padx=0, ipady=2

### 4. 清空信息按钮
- 按钮类型：ttk.Button
- 文本："清空信息"
- 布局：pack(side="right", padx=10)
- 功能：清空信息显示面板的所有内容

## 功能实现细节

### 1. 阈值变量管理
- 匹配阈值变量：self.match_threshold = 0.8
- NMS阈值变量：self.nms_threshold = 0.3

### 2. 增加匹配阈值函数
```python
def increase_match_threshold(self):
    current = float(self.match_threshold_var.get())
    if current < 0.9:
        new_value = round(current + 0.1, 1)
        self.match_threshold_var.set(f"{new_value:.1f}")
        self.match_threshold = new_value
        # 记录日志信息
        self.log_message(f"[信息] 匹配阈值已调整为: {new_value:.1f}", "h_default")
```

### 3. 减少匹配阈值函数
```python
def decrease_match_threshold(self):
    current = float(self.match_threshold_var.get())
    if current > 0.5:
        new_value = round(current - 0.1, 1)
        self.match_threshold_var.set(f"{new_value:.1f}")
        self.match_threshold = new_value
        # 记录日志信息
        self.log_message(f"[信息] 匹配阈值已调整为: {new_value:.1f}", "h_default")
```

### 4. 增加NMS阈值函数
```python
def increase_nms_threshold(self):
    current = float(self.nms_threshold_var.get())
    if current < 0.9:
        new_value = round(current + 0.1, 1)
        self.nms_threshold_var.set(f"{new_value:.1f}")
        self.nms_threshold = new_value
        # 记录日志信息
        self.log_message(f"[信息] NMS阈值已调整为: {new_value:.1f}", "h_default")
```

### 5. 减少NMS阈值函数
```python
def decrease_nms_threshold(self):
    current = float(self.nms_threshold_var.get())
    if current > 0.1:
        new_value = round(current - 0.1, 1)
        self.nms_threshold_var.set(f"{new_value:.1f}")
        self.nms_threshold = new_value
        # 记录日志信息
        self.log_message(f"[信息] NMS阈值已调整为: {new_value:.1f}", "h_default")
```

### 6. 清空信息功能
```python
def clear_info_panel(self):
    self.info_text.config(state='normal')
    self.info_text.delete(1.0, tk.END)
    self.info_text.config(state='disabled')
    # 显示清空确认信息
    self.log_message("[信息] 信息面板已清空。", "h_default")
```

## 布局结构示例
```
阈值调节框架 (height=40)
├── 匹配阈值区域
│   ├── Label: "匹配阈值:"
│   ├── Entry: 显示当前值
│   └── 按钮框架
│       ├── Button "▲" (增加)
│       └── Button "▼" (减少)
├── NMS阈值区域
│   ├── Label: "NMS阈值:"
│   ├── Entry: 显示当前值
│   └── 按钮框架
│       ├── Button "▲" (增加)
│       └── Button "▼" (减少)
└── 清空信息按钮 (右侧对齐)
    └── Button: "清空信息"
```

## 样式和视觉规范
- 按钮宽度：2字符
- 输入框宽度：5字符
- 按钮内边距：ipady=2
- 按钮外边距：pady=0, padx=0
- 框架内边距：padx=10
- 框架外边距：pady=5
- 箭头按钮水平排列（side="left"）
- 清空按钮右侧对齐（side="right"）

## 注意事项
1. 所有阈值调整后应立即更新对应的变量值
2. 阈值调整应有上下限检查
3. 每次调整后应记录日志信息
4. 输入框应设置为只读状态，防止用户手动输入
5. 按钮应使用pack_propagate(False)保持固定大小
6. 清空信息按钮应正确绑定清空功能

## 集成要点
1. 确保阈值变量在主应用中可访问
2. 确保日志记录功能可用
3. 确保清空信息功能与信息面板正确连接
4. 确保阈值在识别功能中被正确使用