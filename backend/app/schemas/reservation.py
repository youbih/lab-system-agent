from pydantic import BaseModel
from datetime import datetime
from pydantic import ConfigDict

class ReservationCreateRequest(BaseModel):
    lab_id:int
    equipment_id:int|None=None
    # start_at 和 end_at 的类型是 datetime，包含完整的日期和时间：年、月、日、时、分、秒
    start_at: datetime
    end_at: datetime
    remark:str |None=None
    reservation_type: int  # 0仅实验室 1仅设备 2实验室+设备


class ReservationResponse(BaseModel):
    id: int
    user_id: int
    user_name: str | None = None
    lab_id: int
    lab_name: str | None = None
    equipment_id: int | None = None
    equipment_name: str | None = None
    start_at: datetime
    end_at: datetime
    remark: str | None = None
    status: int
    reservation_type: int=0
    model_config=ConfigDict(from_attributes=True)


class ReservationAuditRequest(BaseModel):
    status: int  # 1-通过 2-拒绝
