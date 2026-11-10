from pydantic import BaseModel
from datetime import datetime

class ReservationCreateRequest(BaseModel):
    lab_id:int
    equipment_id:int|None=None
    # start_at 和 end_at 的类型是 datetime，包含完整的日期和时间：年、月、日、时、分、秒
    start_at: datetime
    end_at: datetime
    remark:str |None=None
