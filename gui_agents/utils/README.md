# GUI Agents Utilities

这个目录包含了GUI Agents项目的各种工具函数，用于提高代码的复用性和可维护性。

## 文件结构

```
gui_agents/utils/
├── README.md           # 本文档
├── file_utils.py       # 文件操作工具
├── id_utils.py         # ID生成工具
└── common_utils.py     # 其他通用工具
```

## file_utils.py - 文件操作工具

### 文件锁机制

```python
from gui_agents.utils.file_utils import locked

# 跨平台文件锁，支持Windows和Unix系统
with locked(file_path, "w") as f:
    f.write("content")
```

### 安全JSON操作

```python
from gui_agents.utils.file_utils import safe_write_json, safe_read_json

# 安全写入JSON文件（原子操作）
safe_write_json(file_path, data)

# 安全读取JSON文件
data = safe_read_json(file_path, default={})
```

### 安全文本操作

```python
from gui_agents.utils.file_utils import safe_write_text, safe_read_text

# 安全写入文本文件（UTF-8编码）
safe_write_text(file_path, content)

# 安全读取文本文件（自动编码检测）
content = safe_read_text(file_path)
```

### 文件管理工具

```python
from gui_agents.utils.file_utils import ensure_directory, backup_file

# 确保目录存在
ensure_directory(path)

# 创建文件备份
backup_path = backup_file(file_path, ".backup")
```

## id_utils.py - ID生成工具

### UUID生成

```python
from gui_agents.utils.id_utils import generate_uuid, generate_short_id

# 生成完整UUID
uuid_str = generate_uuid()  # "550e8400-e29b-41d4-a716-446655440000"

# 生成短ID
short_id = generate_short_id("task", 8)  # "task550e8400"
```

### 时间戳ID

```python
from gui_agents.utils.id_utils import generate_timestamp_id

# 基于时间戳的ID
ts_id = generate_timestamp_id("event")  # "event1755576661494"
```

### 哈希ID

```python
from gui_agents.utils.id_utils import generate_hash_id

# 基于内容哈希的ID
hash_id = generate_hash_id("some content", "hash", 8)  # "hasha1b2c3d4"
```

### 复合ID

```python
from gui_agents.utils.id_utils import generate_composite_id

# 复合ID（前缀+时间戳+UUID）
composite_id = generate_composite_id("task", True, True, "_")  # "task_1755576661494_550e8400"
```

## 在NewGlobalState中的使用

新的`NewGlobalState`类已经重构，使用这些工具函数：

```python
from gui_agents.utils.file_utils import safe_write_json, safe_read_json
from gui_agents.utils.id_utils import generate_uuid

class NewGlobalState:
    def __init__(self, ...):
        self.task_id = task_id or f"task-{generate_uuid()[:8]}"
    
    def set_task(self, task_data):
        safe_write_json(self.task_path, task_data)
    
    def get_task(self):
        return safe_read_json(self.task_path, {})
```

## 优势

1. **代码复用**: 公共功能集中管理，避免重复代码
2. **跨平台兼容**: 文件锁等机制自动适配不同操作系统
3. **错误处理**: 统一的错误处理和日志记录
4. **编码安全**: 自动处理Unicode编码问题
5. **原子操作**: JSON写入使用临时文件确保原子性
6. **易于维护**: 功能模块化，便于测试和更新

## 注意事项

- 文件锁机制在Windows和Unix系统上使用不同的实现
- JSON操作包含编码回退机制，确保兼容性
- ID生成函数中的`generate_sequential_id`不是线程安全的
- 所有文件操作都包含适当的错误处理和日志记录 