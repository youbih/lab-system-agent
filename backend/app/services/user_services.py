from app.models.user import User
from app.schemas.user import UserResponse
from sqlalchemy.orm import Session
from app.schemas.user import UserUpdateRequest,UserResponse,PasswordUpdateRequest
from app.utils.password import verify_password, hash_password
from app.common.exceptions import BusinessException
def get_user_info(user: User)-> UserResponse:
    return UserResponse.model_validate(user)


def update_user_info(db:Session,user:User,data:UserUpdateRequest):
    user_dict=data.model_dump(exclude_none=True)
    for field,value in user_dict.items():
        setattr(user,field,value)
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)

def update_password(db:Session,user:User,data:PasswordUpdateRequest):
     """修改用户的密码"""
     if not verify_password(data.old_password,user.password):
         raise BusinessException(message="原密码错误")
     if data.old_password ==data.new_password:
         raise BusinessException(message="新密码不能与旧密码一致")
     user.password=hash_password(data.new_password)
     db.commit()
