# 开发后端文件上传 API

> 对应课程:第 10 节
> 对应项目:`agent-lab/lab-system-agent/backend`
> 涉及文件:`app/api/files.py`(新增)、`app/config.py`(新增配置)、`app/main.py`(挂载静态目录)
> 验证方式:curl 上传 + 浏览器访问图片 URL
> 阅读建议：按小节阅读，配合项目源码与示例理解执行过程。

---

## 阅读说明：代码版本与讲解方式

这份笔记根据原课程记录与当前项目源码整理，不代表拥有每节课的完整历史快照。保留原记录中的课程重点和排错经历；历史代码、当前实现、建议改进会分别说明。未在对话或原记录中确认的测试，不写成新增的实测结论。

代码按“完整片段 → 按执行顺序拆解 → 输入/返回值例子 → 页面或接口效果”阅读。仅有一两行的导入、配置或重复片段使用紧接代码的说明，避免反复展开相同逻辑。

**本节版本对应：** 上传函数使用当前源码，包含 FileResponse；头像绑定到用户资料属于第 11 节。原文的原始返回记录作为历史证据保留，不把本次文档改写当成重新实测。

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

**按执行顺序拆解：**

#### 第一步：用路径对象确定保存目录

```python
UPLOAD_DIR = BASE_DIR / "uploads"
```

BASE_DIR 指 backend 根目录，Path 的 / 运算符用于拼接路径，不是字符串除法。UPLOAD_DIR 是服务器磁盘路径，不是供浏览器请求的 URL。

#### 第二步：确保目录存在

```python
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
```

parents=True 允许创建缺失的上级目录，exist_ok=True 允许目录已经存在。配置模块被导入时就会执行这一步，不是每次点上传才临时选择目录。

#### 第三步：声明体积和后缀规则

```python
MAX_FILE_SIZE = 100 * 1024 * 1024
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}
```

上面后缀集合是节选，完整集合见 config.py。MAX_FILE_SIZE 的单位为字节；允许哪些后缀和允许多少字节是两种独立检查，不会仅因定义常量就自动校验，接口函数还需要使用它们。

**把结果连起来：** 配置负责提供规则与磁盘位置，具体上传函数负责执行校验和写文件。


要点:

- `BASE_DIR / "uploads"`:用 pathlib 拼路径,跨平台不出错
- `mkdir(exist_ok=True)`:启动时自动建目录,不存在才建,幂等
- 后缀白名单:防止别人上传 `.exe`、`.py` 这类危险文件

---

## 第二章 上传接口(app/api/files.py)

### 2.1 当前源码对应的完整上传接口

```python
from fastapi import APIRouter, UploadFile, File
from app.common.exceptions import BusinessException
from app.common.response import Response
from app.schemas.files import FileResponse
import os
from pathlib import Path
from app.config import ALLOWED_EXTENSIONS
from app.config import MAX_FILE_SIZE
from app.config import UPLOAD_DIR
import time
import uuid
import shutil

router=APIRouter(prefix="/files",tags=["文件管理"])

@router.post("/upload")
def upload(file:UploadFile=File(...)):

    if not file.filename:
        raise BusinessException(message="文件名不能为空")
    # 原始的文件名 用户头像.jpg
    original_name=os.path.basename(file.filename)
    # 文件后缀 .jpg
    ext=Path(original_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise BusinessException(message=f"不支持的文件后缀:{ext}")
    
    # 文件大小校验
    if file.size and file.size > MAX_FILE_SIZE:
        raise BusinessException(
            message=f"文件不能超过{MAX_FILE_SIZE //1024//1024}MB"
        )

    # 设置喂一的文件名称
    disk_name=f"{int(time.time() *1000)}_{uuid.uuid4().hex[:8]}{ext}"
    #文件存储的实际路径
    save_path =UPLOAD_DIR /disk_name

    #流式写文件
    with open(save_path,"wb") as f:
        shutil.copyfileobj(file.file,f)

    return Response.success(
    data=FileResponse(
        original_name=original_name,
        disk_name=disk_name,
        size=file.size,
        url=f"/uploads/{disk_name}",
    )
)
```

**按执行顺序拆解：**

#### 第一步：接收上传文件并检查名称

```python
def upload(file: UploadFile = File(...)):
    if not file.filename:
        raise BusinessException(message="文件名不能为空")
```

装饰器与路由前缀组合成 POST /api/files/upload。UploadFile/File 来自 FastAPI，file 是 multipart 中名为 file 的字段。File(...) 表示必填；filename 缺失就中断，不进入写文件逻辑。

#### 第二步：提取文件名与后缀

```python
original_name = os.path.basename(file.filename)
ext = Path(original_name).suffix.lower()
```

basename 提取文件名，suffix 取最后一个后缀，lower 统一大小写。比如示例文件 Avatar.JPG 得到 .jpg。后续不使用原始文件名作为保存路径，降低重名与路径拼接风险。后缀检查不等于文件内容验证。

#### 第三步：检查后缀与已知大小

```python
if ext not in ALLOWED_EXTENSIONS:
    raise BusinessException(message=f"不支持的文件后缀:{ext}")
if file.size and file.size > MAX_FILE_SIZE:
    raise BusinessException(message="文件过大")
```

这是校验核心的节选，实际错误文案按完整代码。后缀不允许或已知大小超限都不写文件。当前大小判断依赖 file.size；如果没有大小信息，这个条件不会实现逐块计数限流。它也不能保证整个 HTTP 请求被提前拒绝。

#### 第四步：生成磁盘文件名与完整路径

```python
disk_name = f"{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}{ext}"
save_path = UPLOAD_DIR / disk_name
```

毫秒时间戳加 UUID 片段降低碰撞概率，后缀沿用通过检查的 ext。这是工程上的重名规避，不是数学保证绝对唯一；当前 open 的 wb 模式遇到同名会覆盖。

#### 第五步：以二进制方式复制到磁盘

```python
with open(save_path, "wb") as f:
    shutil.copyfileobj(file.file, f)
```

with 在结束时关闭目标文件；wb 表示二进制写入；file.file 是上传对象提供的文件流，copyfileobj 分块复制。它避免应用代码一次 read 全部数据，但不自动做大小检查或保证网络接收阶段没有资源开销。

#### 第六步：包装文件元信息并返回

```python
return Response.success(data=FileResponse(
    original_name=original_name,
    disk_name=disk_name,
    size=file.size,
    url=f"/uploads/{disk_name}"
))
```

FileResponse 是项目 schema，声明原文件名、磁盘文件名、大小和 URL。URL 是供前端显示的路径，不能用服务器绝对磁盘路径代替。当前 FileResponse.size 声明为 int；若实际拿不到 size，还需考虑该边界，不能认为已完整覆盖。

**把结果连起来：** 文件参数 → 校验 → 改名 → 写磁盘 → 返回元信息；当前上传不要求鉴权，也不会自动把 URL 保存到用户表。


### 2.2 五个关键知识点

**① `UploadFile = File(...)` —— FastAPI 接收文件的固定写法**

```python
def upload(file: UploadFile = File(...)):
```

**这段代码怎样执行：** 这是函数签名节选，不是可以单独执行的完整函数。UploadFile 为上传对象提供 filename/size/file；File(...) 让框架从 multipart 的 file 字段读取必填文件。curl 用 -F，前端用 FormData，不是把文件路径作为普通 JSON 字符串发过去。


- `File(...)` 告诉 FastAPI:从请求的 multipart 表单里取文件
- `...`(Ellipsis)表示"必填"
- 前端/curl 用 `multipart/form-data` 格式传(curl 的 `-F` 就是这个格式)

**② 为什么文件名要"换名"**

直接用用户上传的文件名存盘有两个风险:重名覆盖(两个人都传 `1.jpg`)、路径注入(文件名里带 `../`)。
解决:`时间戳_UUID前8位.后缀`,降低重名风险，并避免直接把用户提供的路径用于磁盘写入；不代表已经完成文件内容和所有安全校验。

**③ `shutil.copyfileobj` —— 流式写入**

```python
shutil.copyfileobj(file.file, f)
```

**这段代码怎样执行：** 调用前源流 file.file 和已打开的目标流 f 都必须存在。copyfileobj 将源的内容逐块读写到目标，结束时目标流由外层 with 关闭。它负责复制，不负责判断这是真图片、处理授权或限制上传总大小。


一块一块地复制,不是一次性读进内存。分块复制可以避免这里一次性读取整个文件，但本接口配置了大小限制，且上传解析、磁盘容量和并发仍有资源边界。不要把这个写法理解成允许无限大的上传。

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

**按执行顺序拆解：**

#### 第一步：导入静态文件工具和目录

```python
from fastapi.staticfiles import StaticFiles
from app.config import UPLOAD_DIR
```

StaticFiles 是框架工具，UPLOAD_DIR 是项目配置的磁盘目录，两者作用不同。这里复用同一个保存目录，避免写到 A、访问却映射到 B。

#### 第二步：把磁盘目录挂在 URL 前缀下

```python
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
```

mount 配置后续访问 /uploads/... 的处理方式。比如接口返回 /uploads/demo.jpg，浏览器访问该路径时，静态服务读取 UPLOAD_DIR/demo.jpg；不是再次调用 POST 上传接口。

#### 第三步：通过开发代理或后端地址访问

浏览器可以访问后端 8000 的 /uploads 路径；当前开发代理也把前端同源 /uploads 转发到后端。相对 URL 最终指向哪个服务器由页面来源与代理配置决定，不是由数据库头像字段自行决定。

**把结果连起来：** 上传负责保存文件，静态挂载负责读取文件，缺少任一环节都无法完成展示。


**作用:把本地文件夹映射成 URL 前缀。**

```
文件存在:  backend/uploads/xxx.jpg
     ↓ mount 的作用
能访问到:  http://localhost:8000/uploads/xxx.jpg
```

没有这行,文件存得再好,外面也访问不到 —— 上传和访问是两个功能,缺一不可。

---

## 第四章 图片存哪了：本地存储的认知

上传的图存在**集群的磁盘**上:

```
backend/uploads/1793766036041_88ae814a.jpg
```

- 不是存在你的 Windows 电脑上,是集群(且 `/work` 是 NFS 共享,四台节点都能看见)
- 上传本质是"复制":源文件不动,uploads/ 里是改了名的副本

**生产环境的替代方案**:对象存储(阿里 OSS / MinIO / S3)—— 文件传到专门存储服务,后端只存 URL。本地磁盘方案的问题:磁盘会满、迁移麻烦、多实例不共享(你的集群恰好靠 NFS 规避了最后一条)。

---

## 第五章 验证（原笔记记录与当前复现方法）

下面的结果沿用原课程笔记记录，本次修订没有重新上传文件。磁盘路径和文件名属于当时示例，复现时换成自己存在的测试图片；上传会在服务器创建文件。

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
