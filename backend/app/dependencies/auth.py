from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.models.user import User
from app.database import get_db
from app.utils.jwt import decode_access_token
from app.common.exceptions import BusinessException

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
)-> User:
    """"JWT token 鉴权验证合法性"""
    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已失效，请重新登录"
        )

    #获取到用户ID
    user_id=payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,detail="无效的登录凭证"
        )
    #从数据库根据用户ID查询用户信息
    user= db.query(User).filter(User.id==user_id).first()
    if not user or user.status!=1:
        raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,detail="用户被禁用"
        )
    return user

# 因为有一些操作要管理员才能执行，所以就需要验证是不是管理员身份

def get_current_admin(current_user:User =Depends(get_current_user)) ->User:
        if current_user.role!="admin":
             raise BusinessException(message="无权限访问",code=403)
        return current_user
