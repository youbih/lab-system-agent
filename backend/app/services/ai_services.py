from openai import OpenAI
from app.common.exceptions import BusinessException
from app.config import settings
from app.schemas.ai import ChatRequest, ChatMessage

SYSTEM_PROMPT = """你是智能实验室预约系统的助手，回答要简洁、准确。

你可以介绍本系统的预约流程：
1. 登录后进入「实验室列表」，选择实验室；设备可选，需要时在同一弹窗中选择
2. 选择日期和时间段后提交，新预约的初始状态为「待审核」
3. 管理员审核后：通过为「已通过」，拒绝为「已拒绝」
4. 学生只能取消「待审核」的预约；已通过、已拒绝、已取消的预约不能取消
5. 预约结束时间已过但仍未审核的记录，会自动变为「已过期」

预约规则：
- 只能预约同一天，开始和结束时间按整点或半点选择
- 至少提前 1 小时预约，最多提前 7 天，单次至少 30 分钟
- 实验室按时间段独占；选择设备时会同时占用实验室和该设备

你无法查询真实的实验室、设备、预约数据，也不能替用户完成预约、取消或审核操作。
如果用户询问某个实验室的开放时间、设备情况或自己的预约记录，请引导他到「实验室列表」「我的预约」页面查看，不要编造具体数据。
"""

def get_client() -> OpenAI:
    if not settings.LLM_API_KEY:
        raise BusinessException(message="未获取到大模型的API Key")
    return OpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL)


def chat(data: ChatRequest,session_id:str):
    """大模型对话"""
    if not data.messages:
        raise BusinessException(message="对话内容为空")
    history = []
    for message in data.messages:
        if message.role in ("user", "assistant") and message.content.strip():
            history.append(message.model_dump())
    if not history:
        raise BusinessException(message="请输入您要对话的内容")

    client = get_client()
    try:
        res=client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[ChatMessage(role="system",content=SYSTEM_PROMPT).model_dump(),
                *history,
                ],
                extra_headers={
                    "x-opencode-session":session_id,
                    "User-Agent":"lab-system-agent/1.0"
                }
            )
        message=res.choices[0].message
        if not message or not message.content or not message.content.strip():
            raise BusinessException(message="大模型没有返回内容")
        return message.content
    except BusinessException:
        raise
    except Exception:
        raise BusinessException(message="大模型调用失败,请稍后重试")
