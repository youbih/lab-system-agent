# 开发后端文件上传 API

> 对应课程:第 10 节
> 对应项目:`agent-lab/lab-system-agent/backend`
> 涉及文件:`app/api/files.py`(新增)、`app/config.py`(新增配置)、`app/main.py`(挂载静态目录)
> 验证方式:curl 上传 + 浏览器访问图片 URL
> 阅读时间:约 25 分钟

---

## 第零章 这节课在干什么

给后端加"文件上传"能力。为后续"用户头像上传"做铺垫。

一个完整的文件上传功能 = **两件事**:

```
① 接收并保存文件   →  POST /api/files/upload(本课主体)
② 能通过 URL 访问  →  app.mount("/uploads", ...) 静态目录映射
```

很多人写完①以为完了,结果前端 `<img>` 打不开图片 —— 因为忘了②。

---

## 第一章 配置项(app/config.py 新增)

```python
UPLOAD_DIR = BASE_DIR / "uploads"          # 文件存哪
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)  # 目录不存在就自动创建
MAX_FILE_SIZE = 100 * 1024 * 1024          # 大小上限:100MB
ALLOWED_EXTENSIONS = { ".jpg", ".jpeg", ".png", ... }  # 允许的后缀白名单
```

要点:

- `BASE_DIR / "uploads"`:用 pathlib 拼路径,跨平台不出错
- `mkdir(exist_ok=True)`:启动时自动建目录,不存在才建,幂等
- 后缀白名单:防止别人上传 `.exe`、`.py` 这类危险文件

---

## 第二章 上传接口(app/api/files.py)

### 2.1 完整代码结构

```python
from fastapi import APIRouter, UploadFile, File
from app.common.response import Response
from app.common.exceptions import BusinessException
from app.config import ALLOWED_EXTENSIONS, MAX_FILE_SIZE, UPLOAD_DIR
import os, time, uuid, shutil
from pathlib import Path

router = APIRouter(prefix="/files", tags=["文件管理"])

@router.post("/upload")
def upload(file: UploadFile = File(...)):
    # ① 文件名不能为空
    if not file.filename:
        raise BusinessException(message="文件名不能为空")

    orignal_name = os.path.basename(file.filename)   # 原始文件名:用户头像.jpg
    ext = Path(orignal_name).suffix.lower()          # 后缀:.jpg
    if ext not in ALLOWED_EXTENSIONS:
        raise BusinessException(message=f"不支持的文件后缀:{ext}")

    # ② 大小校验
    if file.size and file.size > MAX_FILE_SIZE:
        raise BusinessException(message=f"文件不能超过{MAX_FILE_SIZE//1024//1024}MB")

    # ③ 生成唯一的磁盘文件名:时间戳_UUID前8位.后缀
    disk_name = f"{int(time.time()*1000)}_{uuid.uuid4().hex[:8]}{ext}"
    save_path = UPLOAD_DIR / disk_name

    # ④ 流式写入磁盘
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # ⑤ 返回统一格式
    return Response.success(
        data={
            "original_name": orignal_name,
            "disk_name": disk_name,
            "size": file.size,
            "url": f"/uploads/{disk_name}"
        }
    )
```

### 2.2 五个关键知识点

**① `UploadFile = File(...)` —— FastAPI 接收文件的固定写法**

```python
def upload(file: UploadFile = File(...)):
```

- `File(...)` 告诉 FastAPI:从请求的 multipart 表单里取文件
- `...`(Ellipsis)表示"必填"
- 前端/curl 用 `multipart/form-data` 格式传(curl 的 `-F` 就是这个格式)

**② 为什么文件名要"换名"**

直接用用户上传的文件名存盘有两个风险:重名覆盖(两个人都传 `1.jpg`)、路径注入(文件名里带 `../`)。
解决:`时间戳_UUID前8位.后缀`,保证唯一且安全。

**③ `shutil.copyfileobj` —— 流式写入**

```python
shutil.copyfileobj(file.file, f)
```

一块一块地复制,不是一次性读进内存。传 1GB 文件也不会爆内存。**生产级写法**,别用 `f.write(file.file.read())`。

**④ 三层校验的顺序**

```
文件名空? → 后缀合法? → 大小超限?
```

校验全部走 `BusinessException`,自动被全局异常处理器转成统一格式 —— 第 07 课的体系在这里发挥了作用。

**⑤ 返回的 `url` 字段**

`/uploads/xxx.jpg` 是给前端用的"访问路径",配合下面的静态挂载才能打开。

---

## 第三章 静态目录挂载(main.py)

```python
from fastapi.staticfiles import StaticFiles
from app.config import UPLOAD_DIR

# 挂载静态的文件目录 → http://127.0.0.1:8000/uploads/xxx.jpg
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
```

**作用:把本地文件夹映射成 URL 前缀。**

```
文件存在:  backend/uploads/xxx.jpg
     ↓ mount 的作用
能访问到:  http://localhost:8000/uploads/xxx.jpg
```

没有这行,文件存得再好,外面也访问不到 —— 上传和访问是两个功能,缺一不可。

---

## 第四章 图片存哪了:本地存储的认知

上传的图存在**集群的磁盘**上:

```
backend/uploads/1793766036041_88ae814a.jpg
```

- 不是存在你的 Windows 电脑上,是集群(且 `/work` 是 NFS 共享,四台节点都能看见)
- 上传本质是"复制":源文件不动,uploads/ 里是改了名的副本

**生产环境的替代方案**:对象存储(阿里 OSS / MinIO / S3)—— 文件传到专门存储服务,后端只存 URL。本地磁盘方案的问题:磁盘会满、迁移麻烦、多实例不共享(你的集群恰好靠 NFS 规避了最后一条)。

---

## 第五章 验证(已实测通过)

```bash
# 上传
curl -X POST http://127.0.0.1:8000/api/files/upload \
  -F "file=@/work/2025/liusiyu/agent-lab/lab-system-agent/backend/pictures/nikki.jpg"

# 实际返回(本课实测):
# {"code":200,"message":"请求成功","data":{
#   "original_name":"nikki.jpg",
#   "disk_name":"1793766036041_88ae814a.jpg",
#   "size":233697,
#   "url":"/uploads/1793766036041_88ae814a.jpg"}}
```

浏览器访问 `http://localhost:8000/uploads/1793766036041_88ae814a.jpg` 能看到图 = 全链路打通。

### `-F` 参数说明

`-F "file=@路径"`:multipart 表单上传;`file` 对应接口参数名,`@` 后面是文件路径。

---

## 第六章 踩坑实录

| 坑 | 症状 | 解法 |
|---|---|---|
| `"size":"file.size,` 引号错位 | SyntaxError | 变量不加引号:"引号里是死文字,变量名要裸奔" |
| 缺 import(Response/UploadFile/File/Path) | NameError | 悬停看提示;Ctrl+. 自动导入 |
| 上传 404 | 路由没有 | ① files_router 要在 api/__init__.py 注册 ② 改完代码重启服务 |
| StaticFiles/UPLOAD_DIR 没导入 | NameError | main.py 补导入 |

---

## 第七章 常见问题

**Q1: `File(...)` 里的 `...` 是什么?**
Python 的 Ellipsis(省略号对象),FastAPI 里表示"必填"。写成 `File(None)` 就是可选。

**Q2: 文件大小 100MB 会不会太大了?**
看你的场景。头像类建议 2~5MB。`MAX_FILE_SIZE` 按业务调。

**Q3: 怎么防止恶意文件?**
本课的后缀白名单是第一道防线。更严格的还要检查文件头(魔数)、杀毒扫描、上传目录禁止执行权限等。学习阶段掌握白名单即可。

**Q4: 上传接口要不要登录?**
生产环境建议要(挂 `Depends(get_current_user)`),否则任何人都能往你服务器传文件。教程没加的话,知道有这个意识即可。

---

## 术语表

| 术语 | 一句话解释 |
|---|---|
| UploadFile | FastAPI 的文件上传对象,带 filename/size/file 属性 |
| multipart/form-data | 表单传文件的 HTTP 格式(curl -F) |
| app.mount | 把本地目录映射成 URL 前缀(静态文件服务) |
| 流式写入 | 分块复制文件,不占内存(shutil.copyfileobj) |
| UUID | 全球唯一标识符,用于防文件名冲突 |
| 对象存储 | OSS/S3/MinIO,生产环境的文件存储方案 |

---

## 本章自检清单

- [ ] 能说清文件上传的两个部分(保存 + 访问)
- [ ] 能解释为什么文件名要用时间戳+UUID 重命名
- [ ] 能解释 copyfileobj 比 read+write 好在哪
- [ ] 能写出三层校验(文件名/后缀/大小)
- [ ] 能解释 app.mount 的作用
- [ ] 能用 curl -F 上传文件并访问返回的 url
- [ ] 知道生产环境用对象存储替代本地磁盘
