"""长任务的协作取消信号。"""


class JobCancelled(Exception):
    """调用方要求在当前检查点停止处理。"""
