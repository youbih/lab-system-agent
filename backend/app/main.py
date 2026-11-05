import sys
from pathlib import Path

# 允许从任意目录启动:把 backend 目录加入模块搜索路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.models.user import User
from app.database import Base,engine
from app.api.auth import router as auth_router
from app.api.user import router as user_router
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware
from app.api import api
from app.config import UPLOAD_DIR
from app.common.exceptions import (
    BusinessException,
    business_exception_handler,
    http_exception_handler,
    validation_exception_handler,
    global_exception_handler
)

Base.metadata.create_all(bind=engine)

app=FastAPI()

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


app.add_middleware(
    CORSMiddleware,  # FastAPI 内置的跨域中间件
    allow_origins=origins,  # 允许的源(用上面那个白名单)
    allow_credentials=True,  # 允许携带 cookie/凭证
    allow_methods=["*"],  # 允许所有方法:GET/POST/PUT/DELETE...
    allow_headers=["*"],  # 允许所有请求头(包括我们的 Authorization)
)


# 注册异常处理器:业务异常 + HTTP 异常都转成统一返回格式
app.add_exception_handler(BusinessException, business_exception_handler)
# 注意:必须注册 starlette 的 HTTPException(fastapi 的是它的子类),
# 否则框架自己抛的 404/405 接不住
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError,validation_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

#挂载静态的文件目录 http://127.0.0.1:8000/uploads/xxx.jpg
app.mount("/uploads",StaticFiles(directory=UPLOAD_DIR),name="uploads")

app.include_router(api)
@app.get("/")
def root():
    return {"message":"FastAPI工程正在运行中"}
