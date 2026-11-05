from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from app.schemas.auth import LoginRequest, LoginResponse
from app.schemas.auth import RegisterRequest
from sqlalchemy.orm import Session
from app.database import get_db
from app.common.response import Response
from app.common.exceptions import (
    BusinessException,
)
from app.services import auth_services

router = APIRouter(prefix="/auth", tags=["权限验证"])


@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    """登录"""
    result=auth_services.login(db,data)
    return Response.success(
        message="登录成功喵",
        data=result
    )


@router.post("/register")
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    """注册"""
    auth_services.register(db, data)
    return Response.success(message="登录成功喵")


# 专门给 Swagger docs 的 Authorize 按钮用的登录入口(OAuth2 表单格式)
@router.post("/token", include_in_schema=False)
def login_for_docs(
    form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):

    data = LoginRequest(username=form.username, password=form.password)
    result=auth_services.login(db,data)

    return {
        # Swagger Authorize 需要这两个顶层字段(OAuth2 规范)
        "access_token": result.token,
        "token_type": "bearer"
    }
